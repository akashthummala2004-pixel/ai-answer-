"""LLM-backed claim extraction and evidence verification via OpenRouter."""

import re
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.errors import LLMError
from app.schemas import VERDICTS, Evidence
from app.services.openrouter import OpenRouterClient, extract_json

MAX_CLAIMS = 25

EXTRACTION_PROMPT = """You are a meticulous fact-checking analyst.
Extract the atomic, independently verifiable factual claims made in the ANSWER.
Rules:
- One fact per claim. Split compound sentences.
- Make each claim self-contained: replace pronouns with the entity they refer to.
- Preserve numbers, dates, names and qualifiers exactly as stated.
- Ignore opinions, greetings, hedging filler, advice and questions.
- At most {max_claims} claims.
Return ONLY a JSON object: {{"claims": [{{"text": "..."}}]}}"""

VERIFICATION_PROMPT = """You verify claims STRICTLY against the numbered EVIDENCE passages supplied.
Never use outside knowledge. For each claim choose exactly one verdict:
- "supported": the evidence explicitly states the claim.
- "contradicted": the evidence explicitly states something incompatible with the claim.
- "unsupported": the evidence does not address the claim.
- "uncertain": the evidence only partially addresses it, is ambiguous, or conflicts internally.
For supported or contradicted verdicts include at least one quote: a contiguous span copied character-for-character
from the evidence passage (do not rephrase it or add words such as the subject).
"confidence" is your certainty in the verdict, a number between 0 and 1 (e.g. 0.95 when the evidence is explicit).
Return ONLY a JSON object:
{"results": [{"claim_index": 0, "verdict": "<verdict>", "confidence": <0-1>,
  "quotes": [{"evidence_id": "E1", "quote": "<exact span>"}], "explanation": "one or two sentences"}]}
Return one result per claim, in order."""


class _ExtractedClaims(BaseModel):
    claims: list[dict[str, Any]]


class _Quote(BaseModel):
    evidence_id: str
    quote: str = Field(max_length=2000)


class _Result(BaseModel):
    claim_index: int
    verdict: str
    confidence: float = 0.5
    quotes: list[_Quote] = []
    explanation: str = ""


class _Results(BaseModel):
    results: list[_Result]


NEAR_MATCH_MIN_COVERAGE = 0.8
NEAR_MATCH_MIN_CHARS = 20


def _normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower().strip("\"'.")


def match_quote(quote: str, evidence: str) -> tuple[str | None, str]:
    """Return (match_type, text_to_show). match_type is "exact", "near" or None.

    "near" means one contiguous span of the evidence covers >= 80% of the quote (models often prepend
    a subject or trim a word). The evidence's own wording is returned so displayed quotes are always real.
    """
    q, e = _normalise(quote), _normalise(evidence)
    if not q:
        return None, quote
    if q in e:
        return "exact", quote
    block = SequenceMatcher(None, q, e, autojunk=False).find_longest_match(0, len(q), 0, len(e))
    if block.size >= NEAR_MATCH_MIN_CHARS and block.size / len(q) >= NEAR_MATCH_MIN_COVERAGE:
        return "near", _original_span(e[block.b: block.b + block.size], evidence)
    return None, quote


def _original_span(normalised_span: str, evidence: str) -> str:
    """Locate a normalised span in the original evidence so it is shown with its real casing."""
    words = normalised_span.split()
    pattern = r"\s+".join(re.escape(w).replace("'", "['‘’]").replace('"', '["“”]') for w in words)
    found = re.search(pattern, evidence, re.IGNORECASE)
    return found.group(0) if found else normalised_span


async def extract_claims(client: OpenRouterClient, answer: str, question: str | None, model: str) -> list[str]:
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}" if question else f"ANSWER:\n{answer}"
    result = await client.chat(
        [{"role": "system", "content": EXTRACTION_PROMPT.format(max_claims=MAX_CLAIMS)},
         {"role": "user", "content": user}],
        model=model, json_mode=True, max_tokens=2000,
    )
    try:
        parsed = _ExtractedClaims.model_validate(extract_json(result.content))
    except ValidationError as exc:
        raise LLMError("The model returned claims in an unexpected format.", kind="invalid_schema") from exc
    claims = [str(c.get("text", "")).strip() for c in parsed.claims]
    claims = [c for c in claims if c][:MAX_CLAIMS]
    if not claims:
        raise LLMError("The model did not identify any factual claims in the answer.", kind="no_claims")
    return claims


async def verify_claims(client: OpenRouterClient, claims: list[str], evidence: list[Evidence],
                        model: str) -> list[dict[str, Any]]:
    evidence_block = "\n\n".join(f"[{e.id}] {e.title}\n{e.content}" for e in evidence)
    claims_block = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    result = await client.chat(
        [{"role": "system", "content": VERIFICATION_PROMPT},
         {"role": "user", "content": f"EVIDENCE:\n{evidence_block}\n\nCLAIMS:\n{claims_block}"}],
        model=model, json_mode=True, max_tokens=4000,
    )
    try:
        parsed = _Results.model_validate(extract_json(result.content))
    except ValidationError as exc:
        raise LLMError("The model returned verification results in an unexpected format.",
                       kind="invalid_schema") from exc

    by_index = {r.claim_index: r for r in parsed.results}
    evidence_by_id = {e.id: e for e in evidence}
    output: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        r = by_index.get(index)
        if r is None:
            output.append({"verdict": "uncertain", "confidence": 0.0, "evidence": [],
                           "explanation": "The model returned no result for this claim; human review required."})
            continue

        verdict = r.verdict.lower().strip()
        notes: list[str] = []
        if verdict not in VERDICTS:
            notes.append(f"Model returned unknown verdict '{r.verdict}'.")
            verdict = "uncertain"

        matches = []
        for q in r.quotes:
            source = evidence_by_id.get(q.evidence_id.strip("[] "))
            match_type, shown = match_quote(q.quote, source.content) if source else (None, q.quote)
            matches.append({
                "evidence_id": source.id if source else q.evidence_id,
                "evidence_title": source.title if source else "Unknown source",
                "quote": shown,
                "quote_verified": match_type is not None,
                "quote_match": match_type or "not_found",
            })

        if verdict in ("supported", "contradicted") and not any(m["quote_verified"] for m in matches):
            notes.append(f"Grounding check: the model marked this '{verdict}' but its cited quote was not found "
                         "in the evidence, so it was downgraded to 'uncertain'.")
            verdict = "uncertain"
        elif any(m["quote_match"] == "near" for m in matches):
            notes.append("Grounding check: the model's quote was near-verbatim; the exact evidence wording is shown.")

        explanation = " ".join([r.explanation.strip(), *notes]).strip() or "No explanation provided."
        output.append({
            "verdict": verdict,
            "confidence": round(max(0.0, min(1.0, r.confidence)), 2),
            "evidence": matches,
            "explanation": explanation,
        })
    return output
