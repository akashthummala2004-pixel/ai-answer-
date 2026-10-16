"""LIVE Smart Verification tests against the running backend (real OpenRouter + real Supabase).

    .venv/Scripts/python scripts/live_smart_test.py <samples-dir> <output-dir> [--failure-backend URL]

Uses only the public Supabase key via the backend and real user sessions. Credentials are never printed.
Creates two test users (mm-av-smart-a/b+<timestamp>@example.com).
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

RESULTS: list[tuple[str, str, str]] = []
ALLOWED = {"supported_by_evidence", "contradicted_by_evidence", "not_independently_verified", "requires_human_review"}


def record(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    print(f"[{status:<7}] {name}{' — ' + detail if detail else ''}", flush=True)


def check(name: str, ok: bool, detail: str = "") -> bool:
    record("PASS" if ok else "FAIL", name, detail)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("out")
    ap.add_argument("--backend", default="http://127.0.0.1:8001")
    ap.add_argument("--failure-backend", default=None, help="backend started with an invalid model, for failure testing")
    args = ap.parse_args()
    S, OUT = Path(args.samples), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    api = httpx.Client(base_url=args.backend, timeout=200)

    stamp = time.strftime("%Y%m%d%H%M%S")
    password = f"Sv-{uuid.uuid4().hex[:14]}!"
    tokens = {}
    for who in ("a", "b"):
        res = api.post("/api/auth/signup", json={"email": f"mm-av-smart-{who}+{stamp}@example.com", "password": password})
        tokens[who] = res.json().get("access_token") if res.status_code == 200 else None
        check(f"Sign-up test user {who.upper()}", bool(tokens[who]), f"HTTP {res.status_code}")
    if not all(tokens.values()):
        return summary()
    A = {"Authorization": f"Bearer {tokens['a']}"}
    B = {"Authorization": f"Bearer {tokens['b']}"}

    def submit(name, text=None, files=(), headers=A, client=api):
        multipart = [("files", (f, (S / f).read_bytes(), "application/octet-stream")) for f in files]
        started = time.time()
        res = client.post("/api/smart-verifications", data={"text": text} if text else {}, files=multipart or None,
                          headers=headers)
        elapsed = time.time() - started
        if res.status_code == 201:
            rec = res.json()
            (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
            return rec, elapsed
        return res, elapsed

    created: list[str] = []
    email = (S / "email.txt").read_text(encoding="utf-8")

    def describe(rec):
        counts = {k: v for k, v in rec["summary"]["counts"].items() if v}
        return (f"{rec['model']}, {rec['duration_ms'] / 1000:.1f}s, risk={rec['analysis']['risk_level']}, "
                f"claims={rec['summary']['total_claims']} {counts}, risks={len(rec['analysis']['risks'])}")

    def common(name, rec, kinds):
        ok = isinstance(rec, dict) and rec.get("version") == 2
        if not check(f"{name}: live analysis saved", ok,
                     describe(rec) if ok else f"HTTP {rec.status_code}: {rec.json().get('detail')}"):
            return False
        created.append(rec["id"])
        check(f"{name}: inputs recorded", [i["kind"] for i in rec["inputs"]] == kinds, str([i["kind"] for i in rec["inputs"]]))
        check(f"{name}: assessments use the four allowed labels", all(c["assessment"] in ALLOWED for c in rec["claims"]))
        unbacked = [c["id"] for c in rec["claims"] if c["assessment"] in ("supported_by_evidence", "contradicted_by_evidence")
                    and not c["evidence"]]
        check(f"{name}: every Supported/Contradicted claim has a verified source", not unbacked, f"unbacked={unbacked}")
        check(f"{name}: no stored document text or image data", "data:image" not in json.dumps(rec))
        return True

    # 1. Text only
    rec, _ = submit("1-text-only", text=email)
    if common("Text-only", rec, ["text"]):
        check("Text-only: no claim marked Supported/Contradicted (single input)",
              all(c["assessment"] not in ("supported_by_evidence", "contradicted_by_evidence") for c in rec["claims"]))
        check("Text-only: suspicious link/urgency flagged as risk", len(rec["analysis"]["risks"]) > 0)
        found = {d["type"] for d in rec["analysis"]["detected_details"]}
        check("Text-only: contact details detected", {"Email address", "Web address", "Amount"} <= found, ", ".join(sorted(found)))

    # 2. PDF only
    rec, _ = submit("2-pdf-only", files=["offer-letter.pdf"])
    if common("PDF-only", rec, ["pdf"]):
        text = json.dumps(rec["analysis"]).lower()
        check("PDF-only: content of the PDF was analysed", "450" in text or "deposit" in text)

    # 3. Image only
    rec, _ = submit("3-image-only", files=["message-screenshot.png"])
    if common("Image-only", rec, ["image"]):
        text = json.dumps(rec).lower()
        check("Image-only: model read text from the screenshot", "globex" in text or "6-digit" in text or "code" in text)

    # 4. Text + document (cross-check)
    rec, _ = submit("4-text-plus-pdf", text=email, files=["refund-policy.pdf"])
    if common("Text+PDF", rec, ["text", "pdf"]):
        backed = [c for c in rec["claims"] if c["evidence"]]
        check("Text+PDF: at least one claim checked against the uploaded policy", bool(backed),
              "; ".join(f"{c['id']} {c['assessment']} <- \"{c['evidence'][0]['quote'][:60]}\"" for c in backed))

    # 5. Scanned PDF
    rec, _ = submit("5-scanned-pdf", files=["scanned-invoice.pdf"])
    if common("Scanned PDF", rec, ["scanned_pdf"]):
        text = json.dumps(rec).lower()
        check("Scanned PDF: text read from page image", "inv-1042" in text or "1,250" in text or "contoso" in text)
        check("Scanned PDF: limitation stated", any("no text layer" in n for n in rec["limitations"]))

    # 6. Invalid inputs
    for name, files, text in (("Corrupt PDF", ["corrupt.pdf"], None), ("Password-protected PDF", ["locked.pdf"], None),
                              ("Unsupported .txt file", ["notes.txt"], None), ("Empty submission", [], None)):
        res, _ = submit("invalid", text=text, files=files)
        ok = not isinstance(res, dict) and res.status_code == 422
        check(f"Rejected: {name}", ok, res.json().get("detail") if not isinstance(res, dict) else "accepted!")

    # 7. AI failure (real OpenRouter error from an invalid model)
    if args.failure_backend:
        fail = httpx.Client(base_url=args.failure_backend, timeout=120)
        before = len(api.get("/api/verifications", headers=A).json())
        res, _ = submit("failure", text=email, client=fail)
        ok = not isinstance(res, dict) and res.status_code == 502
        check("AI failure shows a clear error (no offline fallback)", ok,
              f"HTTP {res.status_code}: {res.json().get('detail')}" if not isinstance(res, dict) else "unexpectedly succeeded")
        check("AI failure saves nothing", len(api.get("/api/verifications", headers=A).json()) == before)
    else:
        record("SKIPPED", "AI failure handling", "no --failure-backend given")

    # 8. History, review and reports
    listing = api.get("/api/verifications", headers=A).json()
    check("History lists every saved verification", all(i in {r["id"] for r in listing} for i in created),
          f"{len(created)} created, {len(listing)} listed")
    if created:
        rid = created[0]
        detail = api.get(f"/api/verifications/{rid}", headers=A).json()
        claim_id = detail["claims"][0]["id"] if detail["claims"] else None
        if claim_id:
            rv = api.put(f"/api/verifications/{rid}/claims/{claim_id}/review", headers=A,
                         json={"verdict": "requires_human_review", "note": "Live test: confirm with the courier directly"})
            check("Human review saved", rv.status_code == 200 and rv.json()["summary"]["reviewed_claims"] == 1)
        pdf = api.get(f"/api/verifications/{rid}/report", params={"format": "pdf"}, headers=A)
        if check("PDF report generated", pdf.status_code == 200 and pdf.content.startswith(b"%PDF"), f"{len(pdf.content):,} bytes"):
            (OUT / "report-text-only.pdf").write_bytes(pdf.content)
        combo = next((i for i in created if (OUT / "4-text-plus-pdf.json").exists() and
                      json.loads((OUT / "4-text-plus-pdf.json").read_text(encoding="utf-8"))["id"] == i), None)
        if combo:
            (OUT / "report-text-plus-pdf.pdf").write_bytes(api.get(f"/api/verifications/{combo}/report",
                                                                   params={"format": "pdf"}, headers=A).content)
        md = api.get(f"/api/verifications/{rid}/report", params={"format": "markdown"}, headers=A)
        check("Markdown export still works", md.status_code == 200 and "## Claim-by-Claim Analysis" in md.text)
        js = api.get(f"/api/verifications/{rid}/report", params={"format": "json"}, headers=A)
        check("JSON export still works", js.status_code == 200 and js.json()["id"] == rid)

        # 9. Isolation
        b_list = api.get("/api/verifications", headers=B).json()
        check("User B's history excludes A's verifications", not ({r["id"] for r in b_list} & set(created)))
        check("User B cannot open A's verification", api.get(f"/api/verifications/{rid}", headers=B).status_code == 404)
        check("User B cannot download A's PDF report",
              api.get(f"/api/verifications/{rid}/report", params={"format": "pdf"}, headers=B).status_code == 404)
    (OUT / "created-ids.json").write_text(json.dumps(created), encoding="utf-8")
    return summary()


def summary() -> int:
    p = sum(1 for r in RESULTS if r[0] == "PASS")
    f = sum(1 for r in RESULTS if r[0] == "FAIL")
    s = sum(1 for r in RESULTS if r[0] == "SKIPPED")
    print(f"\nLIVE SMART RESULTS: {p} passed, {f} failed, {s} skipped")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
