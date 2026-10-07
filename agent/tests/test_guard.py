"""The passcode and CloudFront origin checks in front of the API."""

import pytest
from fastapi.testclient import TestClient

from homedocs_agent import app as app_module
from homedocs_agent import config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "DEMO_PASSCODE", "open-sesame")
    monkeypatch.setattr(config, "ORIGIN_SECRET", "from-cloudfront")
    return TestClient(app_module.app)


def test_health_needs_no_passcode(client):
    assert client.get("/api/health").status_code == 200


def test_direct_calls_without_cloudfront_header_are_forbidden(client):
    response = client.get("/api/notifications", headers={"x-demo-passcode": "open-sesame"})
    assert response.status_code == 403


def test_wrong_passcode_is_rejected(client):
    response = client.post(
        "/api/speak",
        json={"text": "hi"},
        headers={"x-origin-verify": "from-cloudfront", "x-demo-passcode": "nope"},
    )
    assert response.status_code == 401


def test_warmup_rejects_calls_without_the_schedule_token(client):
    assert client.post("/events", json={"warmup": "guess"}).status_code == 403
    assert client.post("/events").status_code == 403
