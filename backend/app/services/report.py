"""Verification report rendering (Markdown)."""

from typing import Any

from app.services.pipeline import effective_verdict

_ENGINE_LABELS = {
    "live": "LIVE — AI model via OpenRouter",
    "offline-heuristic": "OFFLINE — deterministic lexical heuristic (not an AI model)",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(record: dict[str, Any]) -> str:
    s = record["summary"]
    lines = [
        f"# Verification Report: {record['title']}",
        "",
        "_Mind Masters AI Solutions — AI Answer Verification_",
        "",
        f"- **Report ID:** {record['id']}",
        f"- **Verified at:** {record.get('verified_at') or record.get('created_at')}",
        f"- **Engine:** {_ENGINE_LABELS.get(record['engine_used'], record['engine_used'])}",
    ]
    if record.get("model"):
        lines.append(f"- **Model:** `{record['model']}`")
    if record.get("fallback_reason"):
        lines.append(f"- **Fallback reason:** {record['fallback_reason']}")
    score = s["reliability_score"]
    lines += [
        f"- **Reliability score:** {score if score is not None else 'n/a'} / 100 "
        "(supported = 1, uncertain = 0.5, others = 0)",
        f"- **Claims:** {s['total_claims']} total — "
        + ", ".join(f"{k}: {v}" for k, v in s["counts"].items()),
        f"- **Human-reviewed claims:** {s['reviewed_claims']} · **Awaiting review:** {s['needs_review']}",
        "",
    ]
    if record.get("question"):
        lines += ["## Question", "", record["question"], ""]
    lines += ["## AI Answer Under Review", "", record["answer"], "", "## Claim Summary", "",
              "| # | Claim | Verdict | Confidence | Reviewed |", "|---|---|---|---|---|"]
    for c in record["claims"]:
        reviewed = "yes" if c.get("review") else "no"
        lines.append(f"| {c['id']} | {_cell(c['text'])} | {effective_verdict(c)} | {c['confidence']:.0%} | {reviewed} |")
    lines += ["", "## Claim Details", ""]
    for c in record["claims"]:
        lines += [f"### {c['id']}. {c['text']}", "",
                  f"- **System verdict:** {c['verdict']} ({c['confidence']:.0%} confidence)",
                  f"- **Explanation:** {c['explanation']}"]
        if c.get("review"):
            r = c["review"]
            lines.append(f"- **Reviewer verdict:** {r['verdict']} — {r.get('note') or 'no note'} "
                         f"({r.get('reviewer') or 'reviewer'}, {r['reviewed_at']})")
        for m in c.get("evidence", []):
            match = m.get("quote_match", "exact" if m["quote_verified"] else "not_found")
            flag = {"exact": "verified verbatim", "near": "verified near-verbatim (evidence wording shown)"}.get(
                match, "NOT found in evidence")
            lines.append(f"- **Evidence {m['evidence_id']} ({m['evidence_title']}), {flag}:** > {_cell(m['quote'])}")
        lines.append("")
    lines += ["## Evidence Sources", ""]
    for e in record["evidence"]:
        url = f" — {e['source_url']}" if e.get("source_url") else ""
        lines.append(f"- **{e['id']}: {e['title']}**{url}")
    lines.append("")
    return "\n".join(lines)


def render_markdown_v2(record: dict[str, Any]) -> str:
    """Markdown export for Smart Verification (version 2) records."""
    from app.services.smart.record import ASSESSMENT_LABELS, effective_assessment

    a = record["analysis"]
    labels = {i["id"]: (i["name"] if i["kind"] != "text" else "Submitted text") for i in record.get("inputs", [])}
    lines = [
        f"# Verification Report: {record['title']}", "",
        "_Mind Masters AI Solutions — Smart Verification. AI-assisted assessment; not independent verification._", "",
        f"- **Verification ID:** {record['id']}",
        f"- **Date:** {record.get('verified_at') or record.get('created_at')}",
        f"- **Model:** `{record.get('model')}`",
        f"- **Inputs:** " + "; ".join(labels.values()),
        f"- **Warning-sign level:** {a['risk_level']} (warning signs found, not proof of wrongdoing)",
        "", "## Summary", "", a["summary"], "", "## Overall Assessment", "", a["overall_assessment"], "",
        "## Key Findings", "",
    ]
    lines += [f"- **{f['label']}:** {f['detail']}" + (f" _(source: {labels.get(f['source'])})_" if f.get("source") else "")
              for f in a["key_findings"]] or ["- None"]
    if a.get("detected_details"):
        lines += ["", "Detected automatically (pattern matching, not AI):", ""]
        lines += [f"- {d['type']}: `{d['value']}`" for d in a["detected_details"]]
    lines += ["", "## Potential Risks", ""]
    lines += [f"- **[{r['severity']}] {r['title']}** — {r['detail']}" for r in a["risks"]] or ["- No specific warning signs identified."]
    lines += ["", "## Claim-by-Claim Analysis", "", "| # | Claim | Assessment | Explanation |", "|---|---|---|---|"]
    for c in record["claims"]:
        note = c["explanation"]
        if c.get("review"):
            note += f" **Human review:** {ASSESSMENT_LABELS.get(c['review']['verdict'])} — {c['review'].get('note') or 'no note'}"
        lines.append(f"| {c['id']} | {_cell(c['text'])} | {ASSESSMENT_LABELS[effective_assessment(c)]} | {_cell(note)} |")
    lines += ["", "## Supporting Sources", ""]
    evidence = [(c["id"], e) for c in record["claims"] for e in c.get("evidence", [])]
    lines += [f"- {cid} — {e['label']}: > {_cell(e['quote'])}" for cid, e in evidence] or \
        ["- No independent sources were available for this verification."]
    lines += ["", "## Recommended Next Steps", ""] + [f"{i}. {s}" for i, s in enumerate(a["next_steps"], 1)]
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in record.get("limitations", [])] + [""]
    return "\n".join(lines)
