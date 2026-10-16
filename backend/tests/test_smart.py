"""Smart Verification: extraction, safeguards, API and PDF report. The AI model is MOCKED in these tests."""

import json

import pytest

from app.core.errors import LLMError
from app.services.openrouter import LLMResult, OpenRouterClient
from app.services.smart import capabilities
from app.services.smart.analyze import _check_claim
from app.services.smart.entities import detect
from app.services.smart.extract import InputError, build_parts, text_part
from tests import fixtures

POLICY_PDF = fixtures.text_pdf(["Acme Logistics Refund Policy", "Refunds are issued within 14 days of a valid request.",
                                "Contact: support@acme-logistics.com"])
EMAIL = ("Dear customer, your parcel is held. Pay a $4.99 release fee within 24 hours at http://acme-parcels-release.xyz. "
         "Refunds are issued within 30 days.")


@pytest.fixture(autouse=True)
def vision_supported(monkeypatch):
    async def yes(settings):
        return True
    monkeypatch.setattr(capabilities, "supports_images", yes)
    monkeypatch.setattr("app.routers.verifications.supports_images", yes)


def ai_reply(**overrides):
    body = {
        "title": "Parcel release fee email", "content_type": "email",
        "summary": "An email asking for a release fee.", "overall_assessment": "Several warning signs.",
        "risk_level": "elevated",
        "key_findings": [{"label": "Requested payment", "detail": "$4.99 release fee", "source": "T"}],
        "risks": [{"title": "Urgency", "detail": "24-hour deadline", "severity": "high", "source": "T"}],
        "claims": [
            {"claim": "Refunds are issued within 30 days.", "source": "T", "assessment": "contradicted_by_evidence",
             "explanation": "The policy says 14 days.",
             "evidence": {"input_id": "D1", "quote": "Refunds are issued within 14 days of a valid request."}},
            {"claim": "A release fee is required.", "source": "T", "assessment": "supported_by_evidence",
             "explanation": "Invented support.", "evidence": {"input_id": "D1", "quote": "A release fee of $4.99 applies."}},
            {"claim": "The parcel is held.", "source": "T", "assessment": "not_independently_verified",
             "explanation": "Cannot be checked.", "evidence": None},
        ],
        "next_steps": ["Contact Acme through its official website."],
    }
    body.update(overrides)
    return json.dumps(body)


def mock_ai(monkeypatch, reply=None, error=None, seen=None, cross=None):
    """Mock OpenRouter. `cross` is the second-pass (claim vs evidence) reply; default: nothing found."""
    async def fake_chat(self, messages, **kwargs):
        if seen is not None:
            seen.append(messages)
        if error:
            raise error
        if str(messages[0]["content"]).startswith("You verify claims"):
            claims_block = messages[1]["content"].split("CLAIMS:" + chr(10), 1)[1]
            n = len([line for line in claims_block.splitlines() if line.strip()])
            body = cross or {"results": [{"claim_index": i, "verdict": "unsupported", "confidence": 0.5, "quotes": [],
                                          "explanation": "Not addressed."} for i in range(n)]}
            return LLMResult(content=json.dumps(body), model="test/vision-model", latency_ms=5)
        return LLMResult(content=reply or ai_reply(), model="test/vision-model", latency_ms=5, usage={"total_tokens": 10})
    monkeypatch.setattr(OpenRouterClient, "chat", fake_chat)


# ---- extraction -----------------------------------------------------------------------------

def test_text_pdf_is_extracted():
    parts = build_parts(None, [("policy.pdf", POLICY_PDF)])
    assert parts[0].kind == "pdf" and "14 days" in parts[0].text and parts[0].pages == 1


def test_scanned_pdf_is_rendered_for_vision():
    part = build_parts(None, [("scan.pdf", fixtures.scanned_pdf(["INVOICE 1042", "Total due: $1,250"]))])[0]
    assert part.kind == "scanned_pdf" and len(part.images) == 1 and part.images[0].startswith("data:image/")
    assert any("no text layer" in n for n in part.notes)


def test_image_is_normalised():
    part = build_parts(None, [("shot.png", fixtures.png(["Hello"]))])[0]
    assert part.kind == "image" and part.images[0].startswith("data:image/")


@pytest.mark.parametrize("files,message", [
    ([("notes.txt", b"plain text")], "not a supported file"),
    ([("fake.png", b"%PDF-1.4 broken")], "could not be read"),
    ([("locked.pdf", fixtures.encrypted_pdf())], "password-protected"),
    ([("empty.png", b"")], "is empty"),
    ([("a.png", fixtures.png(["a"]))] * 4, "at most 3"),
])
def test_invalid_inputs_are_rejected(files, message):
    with pytest.raises(InputError, match=message):
        build_parts(None, files)


def test_requires_some_input_and_limits_text():
    with pytest.raises(InputError, match="Enter some text"):
        build_parts("   ", [])
    with pytest.raises(InputError, match="too long"):
        text_part("x" * 20_001)


def test_detect_contact_details():
    found = {(d["type"], d["value"]) for d in detect(EMAIL + " Call +1 415 555 0134 by 12/05/2026.", "T")}
    assert ("Web address", "http://acme-parcels-release.xyz") in found
    assert ("Amount", "$4.99") in found
    assert ("Phone number", "+1 415 555 0134") in found
    assert ("Date", "12/05/2026") in found


# ---- evidence safeguards ----------------------------------------------------------------------

def test_claim_evidence_must_be_real_and_independent():
    parts = {p.id: p for p in build_parts(EMAIL, [("policy.pdf", POLICY_PDF)])}
    ok = _check_claim({"claim": "x", "source": "T", "assessment": "contradicted_by_evidence",
                       "evidence": {"input_id": "D1", "quote": "Refunds are issued within 14 days of a valid request."}}, parts)
    assert ok["assessment"] == "contradicted_by_evidence" and ok["evidence"][0]["label"] == "Document 'policy.pdf'"

    fake = _check_claim({"claim": "x", "source": "T", "assessment": "supported_by_evidence",
                         "evidence": {"input_id": "D1", "quote": "Not in the document at all."}}, parts)
    assert fake["assessment"] == "not_independently_verified" and fake["evidence"] == []

    self_cite = _check_claim({"claim": "x", "source": "T", "assessment": "supported_by_evidence",
                              "evidence": {"input_id": "T", "quote": "Refunds are issued within 30 days."}}, parts)
    assert self_cite["assessment"] == "not_independently_verified" and "not independent" in self_cite["explanation"]

    no_quote = _check_claim({"claim": "x", "source": "T", "assessment": "contradicted_by_evidence", "evidence": None}, parts)
    assert no_quote["assessment"] == "requires_human_review"


# ---- API --------------------------------------------------------------------------------------

def test_smart_verification_api_flow(live_client, monkeypatch):
    seen = []
    mock_ai(monkeypatch, seen=seen)
    res = live_client.post("/api/smart-verifications", data={"text": EMAIL},
                           files=[("files", ("policy.pdf", POLICY_PDF, "application/pdf")),
                                  ("files", ("shot.png", fixtures.png(["Pay now"]), "image/png"))])
    assert res.status_code == 201, res.text
    rec = res.json()
    assert rec["version"] == 2 and rec["engine_used"] == "live" and rec["model"] == "test/vision-model"
    by_id = {c["id"]: c for c in rec["claims"]}
    assert by_id["C1"]["assessment"] == "contradicted_by_evidence"
    # invented quote rejected; the fee claim is then flagged by the high-stakes safety rule
    assert by_id["C2"]["assessment"] == "requires_human_review" and by_id["C2"]["evidence"] == []
    assert rec["summary"]["needs_review"] == 2 and rec["status"] == "needs_review"
    assert [i["kind"] for i in rec["inputs"]] == ["text", "pdf", "image"]
    assert "submitted_text" in rec and "data:image" not in json.dumps(rec)  # images are never stored
    # the model received the text, the PDF text and the image
    user_content = seen[0][1]["content"]
    assert any(c.get("type") == "image_url" for c in user_content)
    assert any("14 days" in c.get("text", "") for c in user_content)

    review = live_client.put(f"/api/verifications/{rec['id']}/claims/C1/review",
                             json={"verdict": "requires_human_review", "note": "Check with Acme"})
    assert review.status_code == 200 and review.json()["summary"]["reviewed_claims"] == 1
    bad = live_client.put(f"/api/verifications/{rec['id']}/claims/C1/review", json={"verdict": "supported"})
    assert bad.status_code == 422  # v1 verdicts are not valid for v2 records

    pdf = live_client.get(f"/api/verifications/{rec['id']}/report?format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    md = live_client.get(f"/api/verifications/{rec['id']}/report?format=markdown").text
    assert "Not Independently Verified" in md and "Check with Acme" in md
    listing = live_client.get("/api/verifications").json()
    assert listing[0]["version"] == 2 and listing[0]["content_type"] == "email"
    assert live_client.get("/api/stats").json()["smart_verifications"] == 1


def test_ai_failure_returns_error_without_fallback(live_client, monkeypatch):
    mock_ai(monkeypatch, error=LLMError("OpenRouter request timed out after 60s.", kind="timeout"))
    res = live_client.post("/api/smart-verifications", data={"text": EMAIL})
    assert res.status_code == 502 and res.json()["kind"] == "timeout"
    assert live_client.get("/api/verifications").json() == []  # nothing saved


def test_images_rejected_when_model_lacks_vision(live_client, monkeypatch):
    async def no(settings):
        return False
    monkeypatch.setattr("app.routers.verifications.supports_images", no)
    mock_ai(monkeypatch)
    res = live_client.post("/api/smart-verifications", files=[("files", ("shot.png", fixtures.png(["x"]), "image/png"))])
    assert res.status_code == 422 and "cannot read images" in res.json()["detail"]


def test_smart_requires_openrouter(client):
    assert client.post("/api/smart-verifications", data={"text": EMAIL}).status_code == 503


def test_invalid_upload_via_api(live_client, monkeypatch):
    mock_ai(monkeypatch)
    res = live_client.post("/api/smart-verifications", files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert res.status_code == 422 and "not a supported file" in res.json()["detail"]


def test_pdf_report_not_offered_for_legacy_records(client):
    from tests.conftest import EIFFEL_PAYLOAD
    rec = client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    assert client.get(f"/api/verifications/{rec['id']}/report?format=pdf").status_code == 400


def test_cross_check_pass_upgrades_with_verified_quote_only(live_client, monkeypatch):
    reply = ai_reply(claims=[
        {"claim": "Refunds are issued within 30 days.", "source": None, "assessment": "supported_by_evidence",
         "explanation": "Stated in the email.", "evidence": None},          # self-support, no quote, no source
        {"claim": "The parcel is held at the depot.", "source": "T", "assessment": "not_independently_verified",
         "explanation": "Cannot be checked.", "evidence": None},
    ])
    cross = {"results": [
        {"claim_index": 0, "verdict": "contradicted", "confidence": 0.9,
         "quotes": [{"evidence_id": "D1", "quote": "Refunds are issued within 14 days of a valid request."}],
         "explanation": "The policy says 14 days."},
        {"claim_index": 1, "verdict": "supported", "confidence": 0.9,
         "quotes": [{"evidence_id": "D1", "quote": "Parcels are held at the depot."}],  # fabricated quote
         "explanation": "Invented."},
    ]}
    mock_ai(monkeypatch, reply=reply, cross=cross)
    rec = live_client.post("/api/smart-verifications", data={"text": EMAIL},
                           files=[("files", ("policy.pdf", POLICY_PDF, "application/pdf"))]).json()
    c1, c2 = rec["claims"]
    assert c1["source"] == "T"  # inferred from the text
    assert c1["assessment"] == "contradicted_by_evidence" and c1["evidence"][0]["input_id"] == "D1"
    assert c2["assessment"] == "not_independently_verified" and c2["evidence"] == []


def test_high_stakes_claims_always_need_human_review(live_client, monkeypatch):
    reply = ai_reply(claims=[{"claim": "Pay a $4.99 release fee within 24 hours.", "source": "T",
                              "assessment": "not_independently_verified", "explanation": "Cannot be checked.",
                              "evidence": None}])
    mock_ai(monkeypatch, reply=reply)
    rec = live_client.post("/api/smart-verifications", data={"text": EMAIL}).json()
    assert rec["claims"][0]["assessment"] == "requires_human_review"
    assert "Flagged automatically" in rec["claims"][0]["explanation"]
