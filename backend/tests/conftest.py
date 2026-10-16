import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App client in offline/local mode with an isolated data directory."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def live_client(client, monkeypatch):
    """Same client, but with an OpenRouter key so the live path is selected (calls are mocked)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-1234567890")
    get_settings.cache_clear()
    return client


EIFFEL_PAYLOAD = {
    "title": "Eiffel Tower facts",
    "question": "Tell me about the Eiffel Tower.",
    "answer": (
        "The Eiffel Tower is located in Paris. It was completed in 1889. "
        "The tower is 500 meters tall. It was designed by Leonardo da Vinci."
    ),
    "evidence": [
        {
            "title": "Encyclopedia entry",
            "content": (
                "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. "
                "It was completed in 1889 for the World's Fair. "
                "The tower is 330 metres tall. "
                "It was designed and built by the company of engineer Gustave Eiffel."
            ),
            "source_url": "https://example.org/eiffel",
        }
    ],
    "engine": "auto",
}
