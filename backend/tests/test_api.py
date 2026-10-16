import json

from app.core.errors import LLMError
from app.services.openrouter import LLMResult, OpenRouterClient, extract_json
from tests.conftest import EIFFEL_PAYLOAD


def test_health_reports_offline_local_mode(client):
    body = client.get("/api/health").json()
    assert body["ai_mode"] == "offline"
    assert body["storage"] == "local"
    assert body["auth_required"] is False


def test_offline_verification_flow(client):
    res = client.post("/api/verifications", json=EIFFEL_PAYLOAD)
    assert res.status_code == 201, res.text
    record = res.json()
    assert record["engine_used"] == "offline-heuristic"
    assert record["fallback_reason"] == "OpenRouter is not configured."
    verdicts = [c["verdict"] for c in record["claims"]]
    assert verdicts == ["supported", "supported", "contradicted", "unsupported"]
    assert record["summary"]["total_claims"] == 4

    listing = client.get("/api/verifications").json()
    assert [r["id"] for r in listing] == [record["id"]]
    assert client.get("/api/stats").json()["verdict_counts"]["contradicted"] == 1


def test_human_review_overrides_verdict(client):
    record = client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    url = f"/api/verifications/{record['id']}/claims/C4/review"
    updated = client.put(url, json={"verdict": "contradicted", "note": "Designed by Eiffel's company."}).json()
    claim = next(c for c in updated["claims"] if c["id"] == "C4")
    assert claim["review"]["verdict"] == "contradicted"
    assert claim["verdict"] == "unsupported"  # original system verdict preserved
    assert updated["summary"]["counts"]["contradicted"] == 2
    assert updated["summary"]["reviewed_claims"] == 1

    cleared = client.delete(url).json()
    assert cleared["summary"]["reviewed_claims"] == 0


def test_report_exports(client):
    record = client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    md = client.get(f"/api/verifications/{record['id']}/report?format=markdown")
    assert md.status_code == 200
    assert "OFFLINE — deterministic lexical heuristic" in md.text
    assert "attachment" in md.headers["content-disposition"]
    js = client.get(f"/api/verifications/{record['id']}/report?format=json")
    assert js.json()["id"] == record["id"]


def test_delete_and_not_found(client):
    record = client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    assert client.delete(f"/api/verifications/{record['id']}").status_code == 204
    assert client.get(f"/api/verifications/{record['id']}").status_code == 404


def test_validation_errors(client):
    bad = {**EIFFEL_PAYLOAD, "evidence": []}
    assert client.post("/api/verifications", json=bad).status_code == 422
    bad = {**EIFFEL_PAYLOAD, "answer": "short"}
    assert client.post("/api/verifications", json=bad).status_code == 422
    bad = {**EIFFEL_PAYLOAD, "model": "bad model; drop"}
    assert client.post("/api/verifications", json=bad).status_code == 422


def test_live_mode_requested_without_key_fails(client):
    res = client.post("/api/verifications", json={**EIFFEL_PAYLOAD, "engine": "live"})
    assert res.status_code == 502
    assert res.json()["kind"] == "not_configured"


def test_live_engine_with_grounding_check(live_client, monkeypatch):
    replies = iter([
        json.dumps({"claims": [{"text": "The Eiffel Tower is in Paris."}, {"text": "The tower is 500 m tall."}]}),
        json.dumps({"results": [
            {"claim_index": 0, "verdict": "supported", "confidence": 0.95,
             "quotes": [{"evidence_id": "E1", "quote": "a wrought-iron lattice tower in Paris, France"}],
             "explanation": "Stated directly."},
            {"claim_index": 1, "verdict": "supported", "confidence": 0.9,
             "quotes": [{"evidence_id": "E1", "quote": "The tower is 500 metres tall."}],
             "explanation": "Hallucinated quote."},
        ]}),
    ])

    async def fake_chat(self, messages, **kwargs):
        return LLMResult(content=next(replies), model="test/model", latency_ms=5)

    monkeypatch.setattr(OpenRouterClient, "chat", fake_chat)
    record = live_client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    assert record["engine_used"] == "live"
    assert record["claims"][0]["verdict"] == "supported"
    assert record["claims"][0]["evidence"][0]["quote_verified"] is True
    # Fabricated quote is caught and the verdict downgraded.
    assert record["claims"][1]["verdict"] == "uncertain"
    assert "Grounding check" in record["claims"][1]["explanation"]


def test_auto_mode_falls_back_when_live_fails(live_client, monkeypatch):
    async def failing_chat(self, messages, **kwargs):
        raise LLMError("OpenRouter request timed out after 60s.", kind="timeout")

    monkeypatch.setattr(OpenRouterClient, "chat", failing_chat)
    record = live_client.post("/api/verifications", json=EIFFEL_PAYLOAD).json()
    assert record["engine_used"] == "offline-heuristic"
    assert "timed out" in record["fallback_reason"]

    res = live_client.post("/api/verifications", json={**EIFFEL_PAYLOAD, "engine": "live"})
    assert res.status_code == 502 and res.json()["kind"] == "timeout"


def test_extract_json_handles_fences():
    assert extract_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_logout_is_a_noop_in_local_mode(client):
    assert client.post("/api/auth/logout").status_code == 204
