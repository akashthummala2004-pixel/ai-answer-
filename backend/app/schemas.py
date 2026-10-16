"""Pydantic models for the verification domain."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Verdict = Literal["supported", "contradicted", "unsupported", "uncertain"]
Engine = Literal["auto", "live", "offline"]
VERDICTS: tuple[str, ...] = ("supported", "contradicted", "unsupported", "uncertain")

MODEL_PATTERN = r"^[A-Za-z0-9._\-/:]+$"


class EvidenceIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=30000)
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("title", "content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("source_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return v


class Evidence(EvidenceIn):
    id: str


class VerificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    question: str | None = Field(default=None, max_length=5000)
    answer: str = Field(min_length=10, max_length=20000)
    evidence: list[EvidenceIn] = Field(min_length=1, max_length=20)
    engine: Engine = "auto"
    model: str | None = Field(default=None, max_length=120, pattern=MODEL_PATTERN)

    @field_validator("title", "answer")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class EvidenceMatch(BaseModel):
    evidence_id: str
    evidence_title: str
    quote: str
    quote_verified: bool
    quote_match: str = "exact"  # "exact" | "near" | "not_found"


class ClaimReview(BaseModel):
    verdict: Verdict
    note: str = ""
    reviewer: str | None = None
    reviewed_at: str


class Claim(BaseModel):
    id: str
    text: str
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    explanation: str
    evidence: list[EvidenceMatch] = []
    review: ClaimReview | None = None


class ReviewIn(BaseModel):
    # Validated per record format in the router (v1 verdicts or v2 assessments).
    verdict: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=2000)


class Summary(BaseModel):
    total_claims: int
    counts: dict[str, int]
    reliability_score: float | None
    reviewed_claims: int
    needs_review: int
