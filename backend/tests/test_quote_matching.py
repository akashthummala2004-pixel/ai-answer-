from app.services.live_engine import match_quote

EVIDENCE = ("The Great Barrier Reef is the world’s largest coral reef system. It lies off the coast of Queensland, "
            "Australia, and stretches for over 2,300 kilometres.")


def test_exact_quote_tolerates_case_and_curly_quotes():
    assert match_quote("the great barrier reef is the world's largest coral reef system.", EVIDENCE)[0] == "exact"


def test_near_verbatim_quote_shows_original_evidence_wording():
    kind, shown = match_quote("The reef stretches for over 2,300 kilometres.", EVIDENCE)
    assert kind == "near"
    assert shown == "stretches for over 2,300 kilometres" and shown in EVIDENCE


def test_fabricated_quote_is_rejected():
    assert match_quote("The Great Barrier Reef is located off the coast of Queensland, Australia.", EVIDENCE)[0] is None
    assert match_quote("The reef stretches for over 5,000 kilometres.", EVIDENCE)[0] is None
