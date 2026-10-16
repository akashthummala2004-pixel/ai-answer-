"""Smart Verification: one structured AI analysis call, then deterministic safeguards on its output."""

import re
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import LLMError
from app.schemas import Evidence
from app.services import live_engine
from app.services.live_engine import match_quote
from app.services.openrouter import OpenRouterClient, extract_json
from app.services.smart.entities import detect
from app.services.smart.extract import InputPart

ASSESSMENTS = ("supported_by_evidence", "contradicted_by_evidence", "not_independently_verified", "requires_human_review")
RISK_LEVELS = ("low", "moderate", "elevated", "high")
CONTENT_TYPES = ("ai_answer", "email", "business_message", "document", "screenshot", "web_content", "other")
SEVERITIES = ("low", "medium", "high")

SYSTEM_PROMPT = """You are a careful verification analyst for Mind Masters AI Solutions. Users submit content such as
AI-generated answers, emails, business messages, documents and screenshots. You produce a cautious, evidence-aware review.

You have NO internet access and NO external databases. You cannot independently confirm facts about the world,
companies, people, websites or events. Your job is to extract and structure what the content says, flag warning signs and
inconsistencies, and recommend how a person can verify it.

Inputs are labelled: [T] typed text, [D1], [D2] documents, [I1], [I2] images or screenshots.

Rules:
1. Use only the supplied inputs. Never invent sources, URLs, citations, quotes, statistics or percentages.
   Read all visible text in images and scanned pages carefully before analysing them.
2. Extract EVERY distinct factual or actionable claim: statements of fact, figures and dates, company or credential
   statements, promises or guarantees, and requests to pay, click, reply or share information. List each requested action
   as its own claim, including where it must be done (e.g. "Payment must be made at <link>"). Typically 3-12 claims.
   When typed text and documents are both supplied, the typed text is the content under review and the documents are
   reference material: take claims from the typed text (and from documents only when there is no typed text, or the
   text asks for the document to be checked). Always give each claim's "source" input id.
3. Assess each claim with exactly one of:
   - "supported_by_evidence": ONLY if a DIFFERENT supplied input explicitly states the same fact. Give that input's id and a
     quote copied character-for-character from it.
   - "contradicted_by_evidence": ONLY if a DIFFERENT supplied input explicitly states something incompatible. Give id + exact quote.
   - "requires_human_review": any request for payment, deposits, bank or card details, passwords or codes; deadlines,
     threats or pressure; legal, medical or identity claims; internally inconsistent claims; anything that should not be
     acted on without checking.
   - "not_independently_verified": every other claim that cannot be checked from the inputs.
   Your general knowledge is NOT evidence. You may say "general knowledge suggests ..." in an explanation, but such a claim
   stays "not_independently_verified" or "requires_human_review".
4. Explanations must be specific: say why the claim matters and exactly what would confirm it (e.g. "check the order on
   the courier's official website"). Avoid generic phrases such as "cannot be verified without additional context".
5. Never state that a company, person or message is fraudulent or a scam. Describe warning signs (for example
   "indicators commonly seen in phishing") and say they need confirmation.
6. Write in plain, professional English. Be concise.

Return ONLY a JSON object:
{"title": "<descriptive title, max 8 words>",
 "content_type": "ai_answer|email|business_message|document|screenshot|web_content|other",
 "summary": "<2-3 neutral sentences describing what was submitted>",
 "overall_assessment": "<3-5 sentences: what it is, what could and could not be verified from the inputs, main concerns>",
 "risk_level": "low|moderate|elevated|high",
 "key_findings": [{"label": "<short label>", "detail": "<the information>", "source": "<input id>"}],
 "risks": [{"title": "<warning sign>", "detail": "<why it matters>", "severity": "low|medium|high", "source": "<input id>"}],
 "claims": [{"claim": "<self-contained factual claim>", "source": "<input id where it appears>",
             "assessment": "<one of the four values>", "explanation": "<1-2 sentences>",
             "evidence": {"input_id": "<id of a DIFFERENT input>", "quote": "<exact quote>"} or null}],
 "next_steps": ["<practical action the user can take>"]}
Limits: up to 10 key_findings, up to 8 risks (may be empty), up to 15 claims, 3-6 next_steps.
"risk_level" reflects how many warning signs you see, not proof of wrongdoing."""


class _Out(BaseModel):
    title: str = ""
    content_type: str = "other"
    summary: str = ""
    overall_assessment: str = ""
    risk_level: str = "moderate"
    key_findings: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    next_steps: list[Any] = []


def _source_label(part: InputPart) -> str:
    return {"text": "Your submitted text", "pdf": f"Document '{part.name}'", "scanned_pdf": f"Scanned document '{part.name}'",
            "image": f"Image '{part.name}'"}[part.kind]


def build_messages(parts: list[InputPart]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": "Submitted inputs follow."}]
    for p in parts:
        if p.kind == "text":
            content.append({"type": "text", "text": f"[T] Typed text:\n{p.text}"})
        elif p.kind == "pdf":
            content.append({"type": "text", "text": f"[{p.id}] Document '{p.name}' ({p.pages} pages, extracted text):\n{p.text}"})
        elif p.kind == "scanned_pdf":
            content.append({"type": "text", "text": f"[{p.id}] Scanned document '{p.name}': {len(p.images)} page image(s) follow."})
            content += [{"type": "image_url", "image_url": {"url": url}} for url in p.images]
        else:
            content.append({"type": "text", "text": f"[{p.id}] Image '{p.name}' follows."})
            content.append({"type": "image_url", "image_url": {"url": p.images[0]}})
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]


def _clean_str(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


def _check_claim(raw: dict[str, Any], parts: dict[str, InputPart]) -> dict[str, Any]:
    """Keep supported/contradicted only when the cited quote is found in a different, readable input."""
    assessment = _clean_str(raw.get("assessment"), 40).lower()
    if assessment not in ASSESSMENTS:
        assessment = "requires_human_review"
    source = _clean_str(raw.get("source"), 10).upper() or None
    explanation = _clean_str(raw.get("explanation"), 1200)
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else None
    sources: list[dict[str, Any]] = []
    note = None

    if assessment in ("supported_by_evidence", "contradicted_by_evidence"):
        ev_id = _clean_str((evidence or {}).get("input_id"), 10).upper()
        quote = _clean_str((evidence or {}).get("quote"), 1500)
        target = parts.get(ev_id)
        if not target or not quote:
            note = "no supporting quote was provided"
        elif ev_id == source:
            note = "the cited evidence is the same input the claim came from, so it is not independent"
        elif not target.text:
            note = f"the cited evidence is in {_source_label(target).lower()}, which cannot be checked automatically"
        else:
            match_type, shown = match_quote(quote, target.text)
            if match_type:
                sources.append({"input_id": ev_id, "label": _source_label(target), "quote": shown, "match": match_type})
            else:
                note = "the quoted evidence was not found in the cited input"
        if note:
            downgraded = "not_independently_verified" if assessment == "supported_by_evidence" else "requires_human_review"
            kind = "supporting" if assessment == "supported_by_evidence" else "contradicting"
            explanation = f"{explanation} (Evidence check: {note}, so it was not accepted as {kind} evidence.)".strip()
            assessment = downgraded

    return {"text": _clean_str(raw.get("claim"), 600), "source": source if source in parts else None,
            "assessment": assessment, "explanation": explanation or "No explanation provided.", "evidence": sources,
            "review": None}


_HIGH_STAKES_RE = re.compile(
    r"(?:[$€£₹]\s?\d)|"
    r"\b(pay|paid|unpaid|payment|fee|fees|dut(?:y|ies)|owed|amount due|deposit|transfer|wire|invoice|bank|"
    r"account (?:number|details)|iban|swift|sort code|"
    r"card|password|passcode|otp|one-time|verification code|\d-digit code|pin|crypto|bitcoin|gift card|"
    r"within \d+ (?:hours?|minutes?|days?)|expires?|urgent|immediately|suspend\w*|destroy\w*|legal action|arrest)\b",
    re.IGNORECASE,
)


def _infer_source(claim: dict[str, Any], parts: list[InputPart]) -> None:
    """Fill in a missing claim source by finding the text-bearing input whose wording best covers the claim."""
    if claim["source"]:
        return
    words = set(re.findall(r"[a-z0-9]{3,}", claim["text"].lower()))
    best, best_score = None, 0.0
    for p in parts:
        if p.text and words:
            score = len(words & set(re.findall(r"[a-z0-9]{3,}", p.text.lower()))) / len(words)
            if score > best_score:
                best, best_score = p.id, score
    if best_score >= 0.6:
        claim["source"] = best


async def _cross_check(client: OpenRouterClient, claims: list[dict[str, Any]], parts: list[InputPart], model: str) -> None:
    """Second pass: check each claim strictly against the OTHER readable inputs with the quote-verified engine."""
    readable = [p for p in parts if p.text]
    if len(readable) < 2:
        return
    pending = [c for c in claims if not c["evidence"] and c["source"]]
    for source in sorted({c["source"] for c in pending}):
        group = [c for c in pending if c["source"] == source]
        evidence = [Evidence(id=p.id, title=_source_label(p), content=p.text) for p in readable if p.id != source]
        if not evidence:
            continue
        results = await live_engine.verify_claims(client, [c["text"] for c in group], evidence, model)
        labels = {e.id: e.title for e in evidence}
        for claim, res in zip(group, results):
            verified = [m for m in res["evidence"] if m["quote_verified"]]
            if res["verdict"] in ("supported", "contradicted") and verified:
                claim["assessment"] = f"{res['verdict']}_by_evidence"
                claim["explanation"] = res["explanation"].split(" Grounding check:")[0].strip()
                claim["evidence"] = [{"input_id": m["evidence_id"], "label": labels.get(m["evidence_id"], m["evidence_title"]),
                                      "quote": m["quote"], "match": m.get("quote_match", "exact")} for m in verified]


def _apply_safety_rule(claim: dict[str, Any]) -> None:
    if claim["assessment"] == "not_independently_verified" and _HIGH_STAKES_RE.search(claim["text"]):
        claim["assessment"] = "requires_human_review"
        claim["explanation"] += (" (Flagged automatically for human review because it involves a payment, account "
                                 "details, codes or a deadline.)")


def limitations(parts: list[InputPart], model: str) -> list[str]:
    notes = [
        "No external search service is connected. Claims are compared only with the material you submitted; "
        "anything that cannot be checked that way is marked Not Independently Verified.",
        f"The analysis was produced by an AI model ({model}). It can be incomplete or wrong and is not legal, "
        "financial or security advice. Confirm important information with the organisation or person concerned "
        "through contact details you already trust.",
    ]
    if len(parts) == 1:
        notes.append("Only one input was submitted, so no claim could be cross-checked against a second source.")
    for p in parts:
        notes += p.notes
    return notes


async def analyze(parts: list[InputPart], settings: Settings) -> dict[str, Any]:
    client = OpenRouterClient(settings)
    model = settings.openrouter_default_model
    started = time.perf_counter()
    result = await client.chat(build_messages(parts), model=model, temperature=0.1, max_tokens=3500, json_mode=True)
    try:
        out = _Out.model_validate(extract_json(result.content))
    except ValidationError as exc:
        raise LLMError("The AI model returned its analysis in an unexpected format. Please try again.",
                       kind="invalid_schema") from exc

    by_id = {p.id: p for p in parts}
    claims = [_check_claim(c, by_id) for c in out.claims[:15] if isinstance(c, dict) and c.get("claim")]
    for claim in claims:
        _infer_source(claim, parts)
    await _cross_check(client, claims, parts, model)  # LLMError propagates: no silent partial results
    for i, claim in enumerate(claims):
        claim["id"] = f"C{i + 1}"
        _apply_safety_rule(claim)

    def src(value: Any) -> str | None:
        value = _clean_str(value, 10).upper()
        return value if value in by_id else None

    detected = []
    for p in parts:
        if p.text:
            detected += detect(p.text, p.id)

    analysis = {
        "title": _clean_str(out.title, 120) or "Verification",
        "content_type": out.content_type if out.content_type in CONTENT_TYPES else "other",
        "summary": _clean_str(out.summary, 1500),
        "overall_assessment": _clean_str(out.overall_assessment, 2500),
        "risk_level": out.risk_level if out.risk_level in RISK_LEVELS else "moderate",
        "key_findings": [{"label": _clean_str(f.get("label"), 80), "detail": _clean_str(f.get("detail"), 600),
                          "source": src(f.get("source"))} for f in out.key_findings[:10] if isinstance(f, dict)],
        "detected_details": detected,
        "risks": [{"title": _clean_str(r.get("title"), 120), "detail": _clean_str(r.get("detail"), 800),
                   "severity": r.get("severity") if r.get("severity") in SEVERITIES else "medium",
                   "source": src(r.get("source"))} for r in out.risks[:8] if isinstance(r, dict) and r.get("title")],
        "next_steps": [_clean_str(s, 400) for s in out.next_steps[:6] if _clean_str(s)],
    }
    return {
        "version": 2,
        "title": analysis["title"],
        "inputs": [p.metadata() for p in parts],
        "submitted_text": next((p.text for p in parts if p.kind == "text"), None),
        "analysis": analysis,
        "claims": claims,
        "limitations": limitations(parts, result.model),
        "engine_used": "live",
        "model": result.model,
        "usage": result.usage,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "is_sample": False,
    }
