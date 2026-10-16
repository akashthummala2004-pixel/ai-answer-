"""LIVE integration test against the real Supabase project and (optionally) OpenRouter.

Not part of the mocked pytest suite. Requires the backend running on port 8001 with backend/.env configured.

    cd ai-answer-verification/backend
    .venv/Scripts/python scripts/live_integration_test.py              # DB, auth and RLS tests (no AI cost)
    .venv/Scripts/python scripts/live_integration_test.py --live-ai    # also one live OpenRouter verification
    .venv/Scripts/python scripts/live_integration_test.py --cleanup    # delete the records this run created

Security: uses only the public anon/publishable key plus real user JWTs (never a service-role key),
so every database call is subject to Row Level Security. Credentials are never printed.
Creates two test users (mm-av-test-a/b+<timestamp>@<domain>); they are not deleted automatically.
"""

import argparse
import base64
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RESULTS: list[tuple[str, str, str]] = []  # (status, name, detail)

EXAMPLE = {
    "title": "[LIVE TEST] Eiffel Tower facts",
    "question": "Tell me about the Eiffel Tower.",
    "answer": "The Eiffel Tower is located in Paris. It was completed in 1889. The tower is 500 meters tall.",
    "evidence": [{"title": "Encyclopedia entry", "content": (
        "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. It was completed in 1889 for the "
        "World's Fair. The tower is 330 metres tall.")}],
}


def record(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    print(f"[{status:<7}] {name}{' — ' + detail if detail else ''}")


def check(name: str, condition: bool, detail: str = "") -> bool:
    record("PASS" if condition else "FAIL", name, detail)
    return condition


def load_env() -> dict[str, str]:
    path = ROOT / ".env"
    if not path.exists():
        sys.exit("backend/.env not found. Create it from .env.example first.")
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def key_kind(key: str) -> str:
    if key.startswith("sb_publishable_"):
        return "publishable"
    if key.startswith("sb_secret_"):
        return "secret"
    if key.count(".") == 2:
        try:
            part = key.split(".")[1] + "=" * (-len(key.split(".")[1]) % 4)
            return f"jwt:{json.loads(base64.urlsafe_b64decode(part)).get('role')}"
        except ValueError:
            return "jwt:unknown"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8001")
    parser.add_argument("--email-domain", default="example.com")
    parser.add_argument("--live-ai", action="store_true", help="also run one verification with engine=live")
    parser.add_argument("--cleanup", action="store_true", help="delete the verification records created by this run")
    args = parser.parse_args()

    env = load_env()
    supa_url = env.get("SUPABASE_URL", "").rstrip("/")
    anon = env.get("SUPABASE_ANON_KEY", "")
    kind = key_kind(anon)
    if kind in ("secret", "jwt:service_role"):
        sys.exit("SUPABASE_ANON_KEY is a privileged key. Replace it with the anon/publishable key; aborting.")
    print(f"Supabase key type: {kind} (value not shown)")

    api = httpx.Client(base_url=args.backend, timeout=180)
    rest = httpx.Client(base_url=f"{supa_url}/rest/v1", timeout=30)
    created: dict[str, list[str]] = {"A": [], "B": []}
    tokens: dict[str, str] = {}
    refresh_tokens: dict[str, str] = {}

    # 1. Backend wiring
    try:
        health = api.get("/api/health").json()
    except httpx.HTTPError:
        sys.exit(f"Backend not reachable at {args.backend}. Start it: .venv/Scripts/uvicorn app.main:app --port 8001")
    check("Backend reports Supabase storage", health.get("storage") == "supabase", f"storage={health.get('storage')}")
    check("Backend requires authentication", health.get("auth_required") is True)
    ai_live = health.get("ai_mode") == "live"
    record("INFO", "OpenRouter configured on backend", "yes" if ai_live else "no (offline engine only)")

    # 2. Anonymous access is blocked
    anon_res = rest.get("/verifications", params={"select": "id", "limit": "1"}, headers={"apikey": anon})
    check("Anonymous Data API access denied", anon_res.status_code in (401, 403),
          f"HTTP {anon_res.status_code}")
    check("Backend rejects requests without a session", api.get("/api/verifications").status_code == 401)

    # 3. Sign up two users via the backend (Supabase Auth)
    stamp = time.strftime("%Y%m%d%H%M%S")
    password = f"Mm-{uuid.uuid4().hex[:12]}!"  # random, never printed
    for who in ("A", "B"):
        email = f"mm-av-test-{who.lower()}+{stamp}@{args.email_domain}"
        res = api.post("/api/auth/signup", json={"email": email, "password": password})
        body = res.json() if res.content else {}
        if res.status_code == 200 and body.get("access_token"):
            tokens[who] = body["access_token"]
            refresh_tokens[who] = body.get("refresh_token") or ""
            check(f"Sign-up user {who}", True, email)
        else:
            check(f"Sign-up user {who}", False, body.get("message") or body.get("detail") or f"HTTP {res.status_code} "
                  "(if email confirmation is on, sign-up returns no session)")
    if len(tokens) < 2:
        return summary()
    login = api.post("/api/auth/login", json={"email": f"mm-av-test-a+{stamp}@{args.email_domain}", "password": password})
    check("Sign-in with password (user A)", login.status_code == 200 and bool(login.json().get("access_token")))

    def auth(who: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens[who]}"}

    # 4. Create / read / update as user A (through the backend, RLS-enforced)
    res = api.post("/api/verifications", json={**EXAMPLE, "engine": "offline"}, headers=auth("A"))
    if not check("A creates a verification", res.status_code == 201, f"HTTP {res.status_code}"):
        return summary()
    rec = res.json()
    created["A"].append(rec["id"])
    listing = api.get("/api/verifications", headers=auth("A")).json()
    check("A lists own verification", any(r["id"] == rec["id"] for r in listing))
    fetched = api.get(f"/api/verifications/{rec['id']}", headers=auth("A"))
    check("A reads own verification", fetched.status_code == 200 and fetched.json()["answer"] == EXAMPLE["answer"])
    upd = api.put(f"/api/verifications/{rec['id']}/claims/C1/review", headers=auth("A"),
                  json={"verdict": "supported", "note": "live test review"})
    check("A updates (human review)", upd.status_code == 200 and upd.json()["claims"][0]["review"]["note"] == "live test review")
    again = api.get(f"/api/verifications/{rec['id']}", headers=auth("A")).json()
    check("Update persisted in Supabase", again["claims"][0]["review"] is not None and again["updated_at"] != rec["updated_at"])

    # 5. Cross-user isolation: B must not see or change A's data
    b_list = api.get("/api/verifications", headers=auth("B")).json()
    check("B's list excludes A's record", all(r["id"] != rec["id"] for r in b_list), f"B sees {len(b_list)} record(s)")
    check("B cannot read A's record", api.get(f"/api/verifications/{rec['id']}", headers=auth("B")).status_code == 404)
    check("B cannot review A's record", api.put(f"/api/verifications/{rec['id']}/claims/C1/review", headers=auth("B"),
                                                json={"verdict": "contradicted", "note": "x"}).status_code == 404)
    check("B cannot delete A's record", api.delete(f"/api/verifications/{rec['id']}", headers=auth("B")).status_code == 404)

    direct = {"apikey": anon, "Authorization": f"Bearer {tokens['B']}", "Prefer": "return=representation"}
    sel = rest.get("/verifications", params={"id": f"eq.{rec['id']}", "select": "id"}, headers=direct)
    check("Direct Data API: B selects A's row -> nothing", sel.status_code == 200 and sel.json() == [])
    patch = rest.patch("/verifications", params={"id": f"eq.{rec['id']}"}, headers=direct, json={"payload": {"hacked": True}})
    check("Direct Data API: B updates A's row -> 0 rows", patch.status_code == 200 and patch.json() == [])
    a_user_id = api.get("/api/auth/me", headers=auth("A")).json()["id"]
    spoof = rest.post("/verifications", headers=direct, json={"user_id": a_user_id, "payload": {"spoof": True}})
    check("Direct Data API: B inserts as A -> rejected by RLS", spoof.status_code in (401, 403), f"HTTP {spoof.status_code}")
    intact = api.get(f"/api/verifications/{rec['id']}", headers=auth("A")).json()
    check("A's record unchanged after B's attempts", "hacked" not in intact and intact["title"] == EXAMPLE["title"])

    # 6. Report exports (owner only)
    md = api.get(f"/api/verifications/{rec['id']}/report", params={"format": "markdown"}, headers=auth("A"))
    check("A exports Markdown report", md.status_code == 200 and EXAMPLE["title"] in md.text
          and "attachment" in md.headers.get("content-disposition", ""))
    js = api.get(f"/api/verifications/{rec['id']}/report", params={"format": "json"}, headers=auth("A"))
    check("A exports JSON report", js.status_code == 200 and js.json()["id"] == rec["id"])
    check("B cannot export A's report", api.get(f"/api/verifications/{rec['id']}/report", headers=auth("B")).status_code == 404)

    # 7. Delete (owner only)
    tmp = api.post("/api/verifications", json={**EXAMPLE, "title": "[LIVE TEST] delete me", "engine": "offline"}, headers=auth("A"))
    if check("A creates a second record to delete", tmp.status_code == 201):
        tmp_id = tmp.json()["id"]
        check("A deletes own record", api.delete(f"/api/verifications/{tmp_id}", headers=auth("A")).status_code == 204)
        check("Deleted record is gone from Supabase", api.get(f"/api/verifications/{tmp_id}", headers=auth("A")).status_code == 404)

    # 8. Optional live OpenRouter verification
    if args.live_ai and not ai_live:
        record("SKIPPED", "Live OpenRouter verification", "OPENROUTER_API_KEY not configured on the backend")
    elif args.live_ai:
        res = api.post("/api/verifications", json={**EXAMPLE, "title": "[LIVE TEST] OpenRouter", "engine": "live"},
                       headers=auth("A"))
        if res.status_code == 201:
            live = res.json()
            created["A"].append(live["id"])
            check("Live OpenRouter verification", live["engine_used"] == "live",
                  f"model={live['model']}, claims={live['summary']['total_claims']}, verdicts={live['summary']['counts']}")
            stored = api.get(f"/api/verifications/{live['id']}", headers=auth("A"))
            check("Live AI result saved in Supabase", stored.status_code == 200 and stored.json()["engine_used"] == "live"
                  and len(stored.json()["claims"]) == live["summary"]["total_claims"])
        else:
            check("Live OpenRouter verification", False, res.json().get("detail", f"HTTP {res.status_code}"))
    else:
        record("SKIPPED", "Live OpenRouter verification", "run with --live-ai")

    # 9. Logout revokes the session (user B)
    check("B logs out", api.post("/api/auth/logout", headers=auth("B")).status_code == 204)
    after = api.get("/api/verifications", headers=auth("B")).status_code
    check("B's access token rejected after logout", after == 401, f"HTTP {after}")
    if refresh_tokens.get("B"):
        ref = api.post("/api/auth/refresh", json={"refresh_token": refresh_tokens["B"]}).status_code
        check("B's refresh token revoked after logout", ref in (400, 401), f"HTTP {ref}")
    still = api.get(f"/api/verifications/{rec['id']}", headers=auth("A")).status_code
    check("A unaffected by B's logout", still == 200)

    # 10. Optional cleanup of records created by this run (test users remain)
    if args.cleanup:
        for rid in created["A"]:
            check(f"Cleanup: A deletes own record {rid[:8]}",
                  api.delete(f"/api/verifications/{rid}", headers=auth("A")).status_code == 204)
    else:
        record("INFO", "Test records kept", f"{len(created['A'])} record(s) owned by test user A (use --cleanup)")
    return summary()


def summary() -> int:
    failed = [r for r in RESULTS if r[0] == "FAIL"]
    passed = [r for r in RESULTS if r[0] == "PASS"]
    skipped = [r for r in RESULTS if r[0] == "SKIPPED"]
    print(f"\nLIVE RESULTS: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
