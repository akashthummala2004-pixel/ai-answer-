"""Verification pipeline: choose engine, run it, build the stored record."""

import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.errors import LLMError
from app.schemas import VERDICTS, Evidence, VerificationCreate
from app.services import live_engine, offline_engine
from app.services.openrouter import OpenRouterClient

REVIEW_CONFIDENCE_THRESHOLD = 0.6


def effective_verdict(claim: dict[str, Any]) -> str:
    review = claim.get("review")
    return review["verdict"] if review else claim["verdict"]


def needs_review(claim: dict[str, Any]) -> bool:
    if claim.get("review"):
        return False
    return claim["verdict"] in ("contradicted", "uncertain") or claim["confidence"] < REVIEW_CONFIDENCE_THRESHOLD


def summarise(claims: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {v: 0 for v in VERDICTS}
    for claim in claims:
        counts[effective_verdict(claim)] += 1
    total = len(claims)
    # Reliability = share of claims supported by evidence; uncertain claims earn half credit.
    score = round(100 * (counts["supported"] + 0.5 * counts["uncertain"]) / total, 1) if total else None
    return {
        "total_claims": total,
        "counts": counts,
        "reliability_score": score,
        "reviewed_claims": sum(1 for c in claims if c.get("review")),
        "needs_review": sum(1 for c in claims if needs_review(c)),
    }


def refresh_record(record: dict[str, Any]) -> dict[str, Any]:
    summary = summarise(record["claims"])
    record["summary"] = summary
    if summary["needs_review"]:
        record["status"] = "needs_review"
    elif summary["reviewed_claims"]:
        record["status"] = "reviewed"
    else:
        record["status"] = "complete"
    return record


def _offline_claims(answer: str, evidence: list[Evidence]) -> list[dict[str, Any]]:
    titles = {e.id: e.title for e in evidence}
    claims = []
    for text in offline_engine.extract_claims(answer):
        r = offline_engine.verify_claim(text, evidence)
        matches = []
        if r.evidence_id and r.quote:
            matches.append({"evidence_id": r.evidence_id, "evidence_title": titles[r.evidence_id],
                            "quote": r.quote, "quote_verified": True, "quote_match": "exact"})
        claims.append({"text": text, "verdict": r.verdict, "confidence": r.confidence,
                       "explanation": r.explanation, "evidence": matches})
    return claims


async def run_verification(body: VerificationCreate, settings: Settings) -> dict[str, Any]:
    evidence = [Evidence(id=f"E{i + 1}", **e.model_dump()) for i, e in enumerate(body.evidence)]
    client = OpenRouterClient(settings)
    model = body.model or settings.openrouter_default_model
    started = time.perf_counter()

    engine_used = "offline-heuristic"
    fallback_reason: str | None = None
    claims: list[dict[str, Any]]

    if body.engine == "offline":
        claims = _offline_claims(body.answer, evidence)
    elif not client.available:
        if body.engine == "live":
            raise LLMError("Live mode requested but OpenRouter is not configured.", kind="not_configured")
        fallback_reason = "OpenRouter is not configured."
        claims = _offline_claims(body.answer, evidence)
    else:
        try:
            texts = await live_engine.extract_claims(client, body.answer, body.question, model)
            results = await live_engine.verify_claims(client, texts, evidence, model)
            claims = [{"text": t, **r} for t, r in zip(texts, results)]
            engine_used = "live"
        except LLMError as exc:
            if body.engine == "live":
                raise
            fallback_reason = exc.message
            claims = _offline_claims(body.answer, evidence)

    for i, claim in enumerate(claims):
        claim["id"] = f"C{i + 1}"
        claim["review"] = None

    record = {
        "title": body.title,
        "question": body.question,
        "answer": body.answer,
        "evidence": [e.model_dump() for e in evidence],
        "engine_requested": body.engine,
        "engine_used": engine_used,
        "model": model if engine_used == "live" else None,
        "fallback_reason": fallback_reason,
        "claims": claims,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "is_sample": False,
    }
    return refresh_record(record)
