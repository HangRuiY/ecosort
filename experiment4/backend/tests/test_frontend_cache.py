"""The HTML entry point must not reuse a stale frontend after API updates."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("url", ["/", "/index.html", "/?launch=regression"])
def test_frontend_entry_cannot_be_stored(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert '<script type="module"' in response.text
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"


def test_conditional_entry_response_also_prevents_storage(client):
    first = client.get("/")
    response = client.get("/", headers={"If-None-Match": first.headers["etag"]})
    assert response.status_code in (200, 304)
    assert "no-store" in response.headers["Cache-Control"]
