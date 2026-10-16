"""Verification CRUD, Smart Verification uploads, human review, reports and analytics.

Two record formats share the `verifications` table:
  * version 1 (no "version" key): evidence-based verification (POST /api/verifications)
  * version 2: Smart Verification of text, PDFs and images (POST /api/smart-verifications)
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.storage import Repository, get_repository
from app.schemas import VERDICTS, ReviewIn, VerificationCreate
from app.services import pipeline
from app.services.report import render_markdown, render_markdown_v2
from app.services.smart import record as smart
from app.services.smart.analyze import ASSESSMENTS, analyze
from app.services.smart.capabilities import RECOMMENDED_VISION_MODELS, supports_images
from app.services.smart.extract import MAX_FILES, MAX_PDF_BYTES, InputError, build_parts
from app.services.smart.report_pdf import render_pdf

TABLE = "verifications"
router = APIRouter(prefix="/api", tags=["verifications"])


async def _get_or_404(repo: Repository, record_id: str) -> dict:
    record = await repo.get(TABLE, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verification not found.")
    return record


def _refresh(record: dict) -> dict:
    return smart.refresh(record) if smart.is_v2(record) else pipeline.refresh_record(record)


def _needs_review(record: dict, claim: dict) -> bool:
    return smart.needs_review(claim) if smart.is_v2(record) else pipeline.needs_review(claim)


def _list_item(r: dict) -> dict:
    item = {k: r.get(k) for k in ("id", "created_at", "title", "engine_used", "model", "status", "summary",
                                  "fallback_reason", "is_sample")}
    item["version"] = r.get("version", 1)
    if smart.is_v2(r):
        item["content_type"] = r["analysis"]["content_type"]
        item["input_kinds"] = [i["kind"] for i in r.get("inputs", [])]
    return item


@router.post("/verifications", status_code=status.HTTP_201_CREATED)
async def create_verification(body: VerificationCreate, settings: Settings = Depends(get_settings),
                              repo: Repository = Depends(get_repository)) -> dict:
    record = await pipeline.run_verification(body, settings)
    return await repo.create(TABLE, record)


@router.post("/smart-verifications", status_code=status.HTTP_201_CREATED)
async def create_smart_verification(text: str | None = Form(default=None),
                                    files: list[UploadFile] = File(default=[]),
                                    settings: Settings = Depends(get_settings),
                                    repo: Repository = Depends(get_repository)) -> dict:
    if not settings.ai_live_available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "AI analysis is unavailable: OpenRouter is not configured on the server.")
    if len(files) > MAX_FILES:
        raise HTTPException(422, f"Upload at most {MAX_FILES} files at a time.")
    uploads = []
    for f in files:
        data = await f.read(MAX_PDF_BYTES + 1)  # never read more than the largest allowed file
        uploads.append((f.filename or "file", data))
    try:
        parts = await asyncio.to_thread(build_parts, text, uploads)
    except InputError as exc:
        raise HTTPException(422, str(exc)) from exc

    if any(p.images for p in parts) and await supports_images(settings) is False:
        raise HTTPException(422, f"The configured AI model ({settings.openrouter_default_model}) cannot read images or "
                                 "scanned pages, so this file cannot be analysed. Text and text-based PDFs still work. "
                                 f"An administrator can set OPENROUTER_DEFAULT_MODEL to an image-capable model such as "
                                 f"{' or '.join(RECOMMENDED_VISION_MODELS)}.")
    record = smart.refresh(await analyze(parts, settings))  # LLMError -> 502 via exception handler, never a fallback
    return await repo.create(TABLE, record)


@router.get("/verifications")
async def list_verifications(repo: Repository = Depends(get_repository)) -> list[dict]:
    return [_list_item(r) for r in await repo.list(TABLE)]


@router.get("/verifications/{record_id}")
async def get_verification(record_id: str, repo: Repository = Depends(get_repository)) -> dict:
    return await _get_or_404(repo, record_id)


@router.delete("/verifications/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification(record_id: str, repo: Repository = Depends(get_repository)) -> Response:
    if not await repo.delete(TABLE, record_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verification not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/verifications/{record_id}/claims/{claim_id}/review")
async def review_claim(record_id: str, claim_id: str, body: ReviewIn,
                       user: CurrentUser = Depends(get_current_user),
                       repo: Repository = Depends(get_repository)) -> dict:
    record = await _get_or_404(repo, record_id)
    allowed = ASSESSMENTS if smart.is_v2(record) else VERDICTS
    if body.verdict not in allowed:
        raise HTTPException(422, f"verdict must be one of: {', '.join(allowed)}")
    claim = next((c for c in record["claims"] if c["id"] == claim_id), None)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found.")
    claim["review"] = {"verdict": body.verdict, "note": body.note.strip(), "reviewer": user.email,
                       "reviewed_at": datetime.now(timezone.utc).isoformat()}
    return await repo.update(TABLE, record_id, _refresh(record))


@router.delete("/verifications/{record_id}/claims/{claim_id}/review")
async def clear_review(record_id: str, claim_id: str, repo: Repository = Depends(get_repository)) -> dict:
    record = await _get_or_404(repo, record_id)
    claim = next((c for c in record["claims"] if c["id"] == claim_id), None)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found.")
    claim["review"] = None
    return await repo.update(TABLE, record_id, _refresh(record))


@router.get("/verifications/{record_id}/report")
async def export_report(record_id: str, format: Literal["markdown", "json", "pdf"] = Query(default="markdown"),
                        repo: Repository = Depends(get_repository)) -> Response:
    record = await _get_or_404(repo, record_id)
    stem = f"verification-report-{record_id[:8]}"
    if format == "json":
        return Response(json.dumps(record, indent=2, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.json"'})
    if format == "pdf":
        if not smart.is_v2(record):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF reports are available for Smart Verifications only.")
        pdf = await asyncio.to_thread(render_pdf, record)
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'})
    text = render_markdown_v2(record) if smart.is_v2(record) else render_markdown(record)
    return Response(text, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.md"'})


@router.get("/review-queue")
async def review_queue(repo: Repository = Depends(get_repository)) -> list[dict]:
    items = []
    for record in await repo.list(TABLE):
        for claim in record["claims"]:
            if _needs_review(record, claim):
                items.append({"verification_id": record["id"], "verification_title": record["title"],
                              "version": record.get("version", 1), "engine_used": record["engine_used"],
                              "created_at": record["created_at"], "claim": claim})
    return items


@router.get("/stats")
async def stats(repo: Repository = Depends(get_repository)) -> dict:
    records = await repo.list(TABLE)
    verdicts = {v: 0 for v in VERDICTS}
    assessments = {a: 0 for a in ASSESSMENTS}
    pending = reviewed = 0
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    for r in records:
        v2 = smart.is_v2(r)
        for c in r["claims"]:
            if v2:
                assessments[smart.effective_assessment(c)] += 1
            else:
                verdicts[pipeline.effective_verdict(c)] += 1
            pending += _needs_review(r, c)
            reviewed += bool(c.get("review"))
    return {
        "total_verifications": len(records),
        "smart_verifications": sum(1 for r in records if smart.is_v2(r)),
        "last_7_days": sum(1 for r in records if (r.get("created_at") or "") >= week_ago),
        "total_claims": sum(len(r["claims"]) for r in records),
        "assessment_counts": assessments,
        "verdict_counts": verdicts,
        "pending_reviews": pending,
        "reviewed_claims": reviewed,
        "last_verification_at": records[0]["created_at"] if records else None,
    }
