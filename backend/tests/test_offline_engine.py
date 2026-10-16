from app.schemas import Evidence
from app.services import offline_engine

EVIDENCE = [Evidence(id="E1", title="Ref", content=(
    "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. It was completed in 1889. "
    "The tower is 330 metres tall. The tower is not open on Christmas Day."
))]


def test_extract_claims_skips_filler_and_questions():
    claims = offline_engine.extract_claims("Sure! The tower is in Paris. Is it tall? I think it is lovely to visit.")
    assert claims == ["The tower is in Paris."]


def test_supported_claim():
    r = offline_engine.verify_claim("The Eiffel Tower is located in Paris.", EVIDENCE)
    assert r.verdict == "supported"
    assert r.confidence <= offline_engine.MAX_CONFIDENCE


def test_number_conflict_is_contradicted():
    r = offline_engine.verify_claim("The tower is 500 meters tall.", EVIDENCE)
    assert r.verdict == "contradicted"
    assert "500" in r.explanation and "330" in r.explanation


def test_negation_conflict_is_contradicted():
    r = offline_engine.verify_claim("The tower is open on Christmas Day.", EVIDENCE)
    assert r.verdict == "contradicted"


def test_unrelated_claim_is_unsupported():
    r = offline_engine.verify_claim("Leonardo da Vinci painted the Mona Lisa.", EVIDENCE)
    assert r.verdict == "unsupported"
