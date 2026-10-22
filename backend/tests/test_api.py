"""End-to-end through the HTTP API in offline mode: recorded responses, no network."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.replay import NNV_SMILES


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "toxitrace_offline", True)
    return TestClient(app)


def test_health_reports_offline_mode(client):
    body = client.get("/api/health").json()
    assert body["mode"] == "offline"
    assert NNV_SMILES in body["demo_inputs"]


@pytest.mark.parametrize("text, dtxsid, in_dsstox", [
    ("62-75-9", "DTXSID7021029", True),
    ("335-67-1", "DTXSID8031865", True),
    (NNV_SMILES, None, False),
])
def test_demo_inputs_resolve_from_recordings(client, text, dtxsid, in_dsstox):
    body = client.post("/api/analyze", json={"chemical_input": text}).json()

    assert body["identity"]["status"] == "resolved"
    assert body["identity"]["dtxsid"] == dtxsid
    assert body["identity"]["in_dsstox"] is in_dsstox
    assert body["trace"], "every result must carry its trace"


def test_unrecorded_input_fails_visibly_instead_of_guessing(client):
    body = client.post("/api/analyze", json={"chemical_input": "50-00-0"}).json()

    assert body["identity"]["status"] == "not_found"
    assert [e["status"] for e in body["trace"]] == ["error", "error"]
    assert "Offline mode" in body["trace"][0]["error"]
    # A failed lookup must not be reported as "not found in the registry" (rule R7's principle).
    assert "lookup in toxindex and pubchem failed" in body["flags"][-1]["message"]


def test_invalid_cas_returns_400(client):
    resp = client.post("/api/analyze", json={"chemical_input": "62-75-8"})
    assert resp.status_code == 400
    assert "check digit" in resp.json()["detail"]


def test_empty_input_returns_422(client):
    assert client.post("/api/analyze", json={"chemical_input": ""}).status_code == 422


def test_depict_returns_svg(client):
    resp = client.get("/api/depict", params={"smiles": NNV_SMILES})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.text.lstrip().startswith("<?xml")


def test_depict_rejects_unparseable_smiles(client):
    assert client.get("/api/depict", params={"smiles": "C1CC"}).status_code == 400
