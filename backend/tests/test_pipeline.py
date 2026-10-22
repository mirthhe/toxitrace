"""The full analysis pipeline on recorded responses, with a tiny synthetic reference dataset."""

import httpx
import pandas as pd
import pytest
import respx

from app import agent, reference
from app.chem import inchikey
from app.config import settings
from app.reference import ReferenceData, fingerprint
from app.replay import NNV_SMILES
from app.schemas import EmaEntry
from tests.conftest import TOXINDEX_TOOLS, fixture, pubchem_url

pytestmark = pytest.mark.anyio

PFDA = "OC(=O)" + "C(F)(F)" * 8 + "C(F)(F)F"


def tiny_reference() -> ReferenceData:
    rows = [
        ("CN(C)N=O", 1, "train"),          # NDMA itself
        ("CCN(C)N=O", 1, "train"),
        ("CN(C=O)N=O", 1, "train"),
        (PFDA, 0, "test"),                 # collides with PFOA in Morgan r2
        ("FC(F)(F)" + "C(F)(F)" * 5 + "F", 0, "validation"),
        ("c1ccccc1", 0, "train"),
    ]
    df = pd.DataFrame(rows, columns=["smiles", "is_mutagen", "split"])
    df["inchikey"] = df["smiles"].map(inchikey)
    ema = {
        inchikey("CN(C)N=O"): EmaEntry(name="N-nitroso-dimethylamine", ai_ng_per_day=96, revision="Rev. 14"),
        inchikey(NNV_SMILES): EmaEntry(name="N-nitroso-varenicline", cpca_category="3",
                                       ai_ng_per_day=400, revision="Rev. 14"),
    }
    return ReferenceData(df, [fingerprint(s) for s in df["smiles"]], ema, "Rev. 14")


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(settings, "toxitrace_offline", True)
    monkeypatch.setattr(reference, "load", tiny_reference)


def rules_fired(result):
    return {(f.rule_id, f.severity) for f in result.flags}


async def test_ndma_supported_positive_but_not_independent(offline):
    result = await agent.run_analysis("62-75-9")

    assert result.summary.label == "supported_positive"
    assert "not independent" in result.summary.text
    assert ("R5", "caution") in rules_fired(result)
    assert result.structural_support.exact_match.split == "train"
    assert result.regulatory.ema.ai_ng_per_day == 96
    assert [e.source for e in result.trace].count("toxindex") == 3


async def test_pfoa_conflicting_with_domain_and_collision_flags(offline):
    result = await agent.run_analysis("335-67-1")

    assert result.summary.label == "conflicting"
    assert "This leans negative" in result.summary.text
    fired = rules_fired(result)
    assert {("R2", "caution"), ("R3", "conflict"), ("R4", "caution"), ("R7", "caution")} <= fired
    assert any("cannot tell them apart" in f.message for f in result.flags)
    assert result.evidence == []
    assert result.regulatory.n_nitroso is False
    assert result.toxicokinetics.status == "not_in_httk"  # the tiny reference has no httk data


async def test_nnv_prediction_only_and_evidence_tool_not_called(offline):
    result = await agent.run_analysis(NNV_SMILES)

    assert result.summary.label == "prediction_only"
    assert [e.tool for e in result.trace if e.source == "toxindex"] == ["tox_chemical_identity", "toxjobs_predict"]
    assert "not in EPA DSSTox" in result.not_retrieved[0].reason
    assert result.regulatory.ema.cpca_category == "3"
    assert ("R6", "caution") in rules_fired(result)
    assert result.identity.name == "N-nitroso-varenicline"
    assert result.toxicokinetics.status == "not_assessed"
    assert any("systematic name" in f.message for f in result.flags)


async def test_missing_reference_data_is_reported_not_skipped(monkeypatch):
    monkeypatch.setattr(settings, "toxitrace_offline", True)
    monkeypatch.setattr(reference, "load", lambda: None)

    result = await agent.run_analysis("62-75-9")

    assert result.structural_support is None
    assert any("not installed" in n.reason for n in result.not_retrieved)
    assert result.regulatory.n_nitroso is True


@respx.mock
async def test_failed_prediction_is_not_retrieved_never_invented(monkeypatch):
    monkeypatch.setattr(reference, "load", tiny_reference)
    respx.post(f"{TOXINDEX_TOOLS}/tox_chemical_identity").mock(
        return_value=httpx.Response(200, json=fixture("toxindex/identity_ndma.json")))
    respx.get(pubchem_url("name", "62-75-9")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/name_62-75-9.json")))
    respx.post(f"{TOXINDEX_TOOLS}/toxjobs_predict").mock(return_value=httpx.Response(429, json={"error": "slow down"}))
    respx.post(f"{TOXINDEX_TOOLS}/tox_genotoxicity").mock(
        return_value=httpx.Response(200, json=fixture("toxindex/genotox_ndma.json")))

    result = await agent.run_analysis("62-75-9")

    assert all(p.source != "AmesFormer-Pro" for p in result.predictions)
    failed = next(n for n in result.not_retrieved if n.source == "AmesFormer-Pro prediction")
    assert "slow down" in failed.reason
    assert next(e for e in result.trace if e.ref == failed.tool_ref).status == "rate_limited"
