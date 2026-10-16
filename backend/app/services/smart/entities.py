"""Deterministic detection of contact and business details. These are pattern matches, not AI output."""

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")),
    ("Web address", re.compile(r"\bhttps?://[^\s<>\"')\]]+", re.IGNORECASE)),
    ("Domain", re.compile(r"\b(?:www\.)?(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|ai|in|uk|us|info|biz|xyz|app|dev|online|site|shop)\b",
                          re.IGNORECASE)),
    ("Phone number", re.compile(r"(?<![\w.])\+?\d[\d\s().-]{7,}\d(?![\w.])")),
    ("Amount", re.compile(r"(?:[$€£₹]|\b(?:USD|EUR|GBP|INR|Rs\.?)\s?)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|million|billion|lakh|crore))?",
                          re.IGNORECASE)),
    ("Date", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|"
                        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4}\b|"
                        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
                        re.IGNORECASE)),
]
MAX_PER_TYPE = 8


def detect(text: str, source: str) -> list[dict]:
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    email_domains = set()
    for label, pattern in _PATTERNS:
        count = 0
        for match in pattern.finditer(text):
            value = match.group(0).strip().rstrip(".,;:")
            if label == "Phone number" and len(re.sub(r"\D", "", value)) < 8:
                continue
            if label == "Email address":
                email_domains.add(value.split("@", 1)[1].lower())
            if label == "Domain" and (value.lower() in email_domains or any(value.lower() in f["value"].lower()
                                                                             for f in found if f["type"] == "Web address")):
                continue  # already shown as part of an email or URL
            key = (label, value.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append({"type": label, "value": value, "source": source})
            count += 1
            if count >= MAX_PER_TYPE:
                break
    return found
