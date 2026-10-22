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


# Public deployment: access code gates live mode (app/mode.py)

@pytest.fixture
def public(monkeypatch):
    from app import mode
    monkeypatch.setattr(settings, "toxitrace_offline", False)  # the deployment is "live" by config
    monkeypatch.setattr(settings, "demo_access_code", "letmein")
    monkeypatch.setattr(settings, "llm_api_key", "would-cost-money")
    mode.live_limit.reset()
    return TestClient(app)


def test_public_visitors_get_offline_replay_and_no_llm(public, monkeypatch):
    from app import narrative

    async def must_not_be_called(payload):
        raise AssertionError("LLM called in public demo mode")

    monkeypatch.setattr(narrative, "_call_llm", must_not_be_called)
    assert public.get("/api/health").json()["mode"] == "offline"

    body = public.post("/api/analyze", json={"chemical_input": "62-75-9"}).json()

    assert body["identity"]["dtxsid"] == "DTXSID7021029"  # served from recordings, no network
    assert body["interpretation"]["source"] == "template"
    assert "Public demo mode" in body["interpretation"]["note"]


def test_wrong_access_code_is_reported_and_stays_offline(public):
    body = public.get("/api/health", headers={"X-Access-Code": "nope"}).json()
    assert body["mode"] == "offline"
    assert body["access_code_rejected"] is True


def test_right_access_code_unlocks_live_mode(public):
    body = public.get("/api/health", headers={"X-Access-Code": "letmein"}).json()
    assert body["mode"] == "live" and body["access_code_rejected"] is False


def test_live_analyses_are_capped_per_hour(public, monkeypatch):
    from app import agent

    async def fake_analysis(text):
        return agent.AnalysisResult(chemical_input=text, endpoint="ames_mutagenicity")

    monkeypatch.setattr("app.main.run_analysis", fake_analysis)
    monkeypatch.setattr(settings, "live_analyses_per_hour", 2)
    headers = {"X-Access-Code": "letmein"}

    codes = [public.post("/api/analyze", json={"chemical_input": "62-75-9"}, headers=headers).status_code
             for _ in range(3)]

    assert codes == [200, 200, 429]
    # Public (offline) requests are never counted against the cap.
    assert public.post("/api/analyze", json={"chemical_input": "62-75-9"}).status_code == 200


def test_backend_does_not_import_rdkit_drawing():
    """RDKit's drawing module needs system graphics libraries missing on serverless hosts
    (libXrender); structures are drawn in the browser with RDKit.js instead."""
    import subprocess
    import sys

    code = "import sys, app.main; sys.exit('rdkit.Chem.Draw' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
