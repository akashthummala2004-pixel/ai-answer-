"""Deterministic lexical verification engine used when OpenRouter is unavailable.

This is NOT an AI model. It extracts sentence-level claims and compares their key terms,
numbers and negations against evidence sentences. Results are labelled "offline-heuristic"
and confidence is capped so they are never mistaken for model judgements.
"""

import re
from dataclasses import dataclass

from app.schemas import Evidence

MAX_CLAIMS = 25
MAX_CONFIDENCE = 0.85

_STOPWORDS = set(
    """a an the and or but if then so of in on at to for from by with about as into onto over under
    is are was were be been being am do does did has have had having it its this that these those
    there here which who whom whose what when where why how than also very just only such can could
    would should may might must will shall i we you he she they them his her their our your my me us
    not no never none nor""".split()
)
_NEGATION_RE = re.compile(
    r"\b(not|no|never|none|neither|nor|cannot|without|isn't|aren't|wasn't|weren't|doesn't|don't|"
    r"didn't|won't|hasn't|haven't|hadn't|can't|couldn't|shouldn't)\b|n't\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_NON_CLAIM_PREFIXES = (
    "i think", "i believe", "in my opinion", "let me", "hope this", "feel free", "here is", "here are",
    "sure", "certainly", "of course", "great question", "please", "note that you", "in summary", "overall,",
)
_SPELLING = {"metre": "meter", "metres": "meters", "kilometre": "kilometer", "kilometres": "kilometers",
             "centre": "center", "colour": "color", "organisation": "organization"}


def _stem(word: str) -> str:
    word = _SPELLING.get(word, word)
    if word.isdigit():
        return word
    for suffix, min_len in (("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if word.endswith(suffix) and len(word) >= min_len and not word.endswith("ss"):
            return word[: -len(suffix)]
    return word


def key_terms(text: str) -> set[str]:
    return {_stem(w) for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1}


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER_RE.findall(text)}


def has_negation(text: str) -> bool:
    return bool(_NEGATION_RE.search(text))


def split_sentences(text: str) -> list[str]:
    parts = []
    for raw in _SENTENCE_SPLIT_RE.split(text):
        sentence = _BULLET_RE.sub("", raw).strip()
        if sentence:
            parts.append(sentence)
    return parts


def extract_claims(answer: str) -> list[str]:
    claims: list[str] = []
    for sentence in split_sentences(answer):
        lowered = sentence.lower()
        if sentence.endswith("?") or len(sentence.split()) < 4:
            continue
        if lowered.startswith(_NON_CLAIM_PREFIXES):
            continue
        if not key_terms(sentence):
            continue
        claims.append(sentence.rstrip())
        if len(claims) >= MAX_CLAIMS:
            break
    return claims


@dataclass
class OfflineResult:
    verdict: str
    confidence: float
    explanation: str
    evidence_id: str | None
    quote: str | None


def verify_claim(claim: str, evidence: list[Evidence]) -> OfflineResult:
    claim_terms = key_terms(claim)
    claim_numbers = numbers(claim)
    claim_negated = has_negation(claim)
    all_evidence_numbers = set().union(*(numbers(e.content) for e in evidence)) if evidence else set()

    best: tuple[float, Evidence, str] | None = None
    for item in evidence:
        sentences = split_sentences(item.content)
        # Single sentences first (preferred on ties), then adjacent pairs so that a sentence
        # starting with a pronoun ("It stretches…") is scored with its antecedent.
        windows = sentences + [f"{a} {b}" for a, b in zip(sentences, sentences[1:])]
        for sentence in windows:
            terms = key_terms(sentence)
            if not terms or not claim_terms:
                continue
            coverage = len(claim_terms & terms) / len(claim_terms)
            if best is None or coverage > best[0]:
                best = (coverage, item, sentence)

    if best is None or best[0] < 0.4:
        coverage = best[0] if best else 0.0
        return OfflineResult(
            verdict="unsupported",
            confidence=round(min(MAX_CONFIDENCE, 0.5 + (0.4 - coverage)), 2),
            explanation=(
                f"Offline heuristic: at most {coverage:.0%} of the claim's key terms appear in any evidence "
                "sentence, so the evidence does not appear to address this claim."
            ),
            evidence_id=best[1].id if best and coverage > 0 else None,
            quote=best[2] if best and coverage > 0 else None,
        )

    coverage, item, sentence = best
    sentence_numbers = numbers(sentence)
    negation_mismatch = claim_negated != has_negation(sentence)
    number_conflict = bool(claim_numbers and sentence_numbers and not (claim_numbers & sentence_numbers))
    numbers_missing = bool(claim_numbers - all_evidence_numbers)

    if coverage >= 0.5 and (negation_mismatch or number_conflict):
        reasons = []
        if number_conflict:
            reasons.append(
                f"the claim states {', '.join(sorted(claim_numbers))} but the evidence states "
                f"{', '.join(sorted(sentence_numbers))}"
            )
        if negation_mismatch:
            reasons.append("one statement is negated and the other is not")
        return OfflineResult(
            verdict="contradicted",
            confidence=round(min(MAX_CONFIDENCE, 0.45 + coverage * 0.4), 2),
            explanation=f"Offline heuristic: closely matching evidence ({coverage:.0%} term overlap) but "
                        f"{' and '.join(reasons)}.",
            evidence_id=item.id,
            quote=sentence,
        )

    if coverage >= 0.7 and not numbers_missing:
        return OfflineResult(
            verdict="supported",
            confidence=round(min(MAX_CONFIDENCE, 0.4 + coverage * 0.45), 2),
            explanation=f"Offline heuristic: {coverage:.0%} of the claim's key terms appear in this evidence "
                        "sentence with consistent numbers and polarity.",
            evidence_id=item.id,
            quote=sentence,
        )

    detail = "some figures in the claim do not appear in the evidence" if numbers_missing else \
        "only part of the claim is reflected in the evidence"
    return OfflineResult(
        verdict="uncertain",
        confidence=round(0.35 + coverage * 0.2, 2),
        explanation=f"Offline heuristic: partial match ({coverage:.0%} term overlap); {detail}. Human review advised.",
        evidence_id=item.id,
        quote=sentence,
    )
