"""Summary/status helpers for Smart Verification (version 2) records."""

from typing import Any

from app.services.smart.analyze import ASSESSMENTS

ASSESSMENT_LABELS = {
    "supported_by_evidence": "Supported by Evidence",
    "contradicted_by_evidence": "Contradicted by Evidence",
    "not_independently_verified": "Not Independently Verified",
    "requires_human_review": "Requires Human Review",
}


def is_v2(record: dict[str, Any]) -> bool:
    return record.get("version") == 2


def effective_assessment(claim: dict[str, Any]) -> str:
    review = claim.get("review")
    return review["verdict"] if review else claim["assessment"]


def needs_review(claim: dict[str, Any]) -> bool:
    return not claim.get("review") and claim["assessment"] in ("requires_human_review", "contradicted_by_evidence")


def refresh(record: dict[str, Any]) -> dict[str, Any]:
    claims = record["claims"]
    counts = {a: 0 for a in ASSESSMENTS}
    for claim in claims:
        counts[effective_assessment(claim)] += 1
    pending = sum(1 for c in claims if needs_review(c))
    reviewed = sum(1 for c in claims if c.get("review"))
    record["summary"] = {
        "total_claims": len(claims),
        "counts": counts,
        "risk_level": record["analysis"]["risk_level"],
        "risk_count": len(record["analysis"]["risks"]),
        "reviewed_claims": reviewed,
        "needs_review": pending,
        "reliability_score": None,  # v2 deliberately reports no score without measured accuracy
    }
    record["status"] = "needs_review" if pending else ("reviewed" if reviewed else "complete")
    return record
