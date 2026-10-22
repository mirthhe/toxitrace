import httpx
import pytest
import respx

from app.identity import InvalidInput, resolve_identity
from app.trace import Tracer
from tests.conftest import TOXINDEX_TOOLS, fixture, pubchem_url

pytestmark = pytest.mark.anyio

IDENTITY_TOOL = f"{TOXINDEX_TOOLS}/tox_chemical_identity"
NNV_SMILES = "O=NN1CC2CC(C1)c1cc3nccnc3cc12"


def mock_dsstox(identifier: str, body: dict):
    respx.post(IDENTITY_TOOL, json={"identifier": identifier}).mock(
        return_value=httpx.Response(200, json=body)
    )


def severities(flags):
    return [(f.rule_id, f.severity) for f in flags]


@respx.mock
async def test_ndma_by_cas_resolves_and_is_confirmed_by_pubchem():
    mock_dsstox("62-75-9", fixture("toxindex/identity_ndma.json"))
    respx.get(pubchem_url("name", "62-75-9")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/name_62-75-9.json")))
    tracer = Tracer()

    identity, flags = await resolve_identity("62-75-9", tracer)

    assert identity.status == "resolved"
    assert identity.dtxsid == "DTXSID7021029"
    assert identity.inchikey == "UMFJAHHVKNCGLG-UHFFFAOYSA-N"
    assert identity.pubchem_cid == 6124
    assert severities(flags) == [("R1", "info")]
    assert [e.source for e in tracer.entries] == ["toxindex", "pubchem", "local"]


@respx.mock
async def test_pfoa_by_cas_resolves():
    mock_dsstox("335-67-1", fixture("toxindex/identity_pfoa.json"))
    respx.get(pubchem_url("name", "335-67-1")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/name_335-67-1.json")))

    identity, flags = await resolve_identity("335-67-1", Tracer())

    assert identity.status == "resolved"
    assert identity.name == "Perfluorooctanoic acid"
    assert identity.pubchem_cid == 9554
    assert severities(flags) == [("R1", "info")]


@respx.mock
async def test_nnv_by_smiles_not_in_dsstox_but_confirmed_by_pubchem():
    mock_dsstox(NNV_SMILES, fixture("toxindex/identity_n-nitroso-varenicline_smiles.json"))
    respx.get(pubchem_url("inchikey", "PTBAEGOZXFWTJH-UHFFFAOYSA-N")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/inchikey_nnv.json")))

    identity, flags = await resolve_identity(NNV_SMILES, Tracer())

    assert identity.status == "resolved"
    assert identity.in_dsstox is False
    assert identity.dtxsid is None
    assert identity.smiles == NNV_SMILES
    assert identity.pubchem_cid == 163880833
    assert severities(flags) == [("R1", "caution"), ("R1", "info")]
    assert "Not in the EPA DSSTox registry" in flags[0].message


@respx.mock
async def test_nnv_by_name_takes_structure_from_pubchem_and_notes_stereo_variant():
    mock_dsstox("N-nitroso-varenicline", fixture("toxindex/identity_n-nitroso-varenicline.json"))
    respx.get(pubchem_url("name", "N-nitroso-varenicline")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/name_nnv.json")))

    identity, flags = await resolve_identity("N-nitroso-varenicline", Tracer())

    assert identity.status == "resolved"
    assert identity.inchikey == "PTBAEGOZXFWTJH-UHFFFAOYSA-N"
    assert any("Structure taken from PubChem" in f.message for f in flags)
    assert any("1 stereo/charge variant" in f.message for f in flags)


@respx.mock
async def test_ambiguous_name_stops_and_lists_candidates():
    # Shape copied from the real identity response; PFOA's acid and anion as ToxIndex's chat found.
    mock_dsstox("PFOA", {"input": "PFOA", "input_type": "name", "total": 2, "matches": [
        {"dtxsid": "DTXSID8031865", "cas": "335-67-1", "name": "Perfluorooctanoic acid",
         "inchikey": "SNGREZUHAYWORS-UHFFFAOYSA-N"},
        {"dtxsid": "DTXSID40892486", "cas": "45285-51-6", "name": "Perfluorooctanoate",
         "inchikey": "SNGREZUHAYWORS-UHFFFAOYSA-M"},
    ]})

    identity, flags = await resolve_identity("PFOA", Tracer())

    assert identity.status == "ambiguous"
    assert [c.dtxsid for c in identity.candidates] == ["DTXSID8031865", "DTXSID40892486"]
    assert severities(flags) == [("R1", "caution")]


@respx.mock
async def test_dsstox_and_pubchem_disagreeing_is_a_conflict():
    mock_dsstox("62-75-9", fixture("toxindex/identity_ndma.json"))
    respx.get(pubchem_url("name", "62-75-9")).mock(  # PubChem answering with PFOA instead
        return_value=httpx.Response(200, json=fixture("pubchem/name_335-67-1.json")))

    _, flags = await resolve_identity("62-75-9", Tracer())

    assert ("R1", "conflict") in severities(flags)


@respx.mock
async def test_unknown_name_is_not_found_without_inventing_a_structure():
    mock_dsstox("notarealchemicalxyz",
                {"input": "notarealchemicalxyz", "input_type": "name", "matches": [], "total": 0})
    respx.get(pubchem_url("name", "notarealchemicalxyz")).mock(
        return_value=httpx.Response(404, json=fixture("pubchem/name_notfound.json")))
    tracer = Tracer()

    identity, flags = await resolve_identity("notarealchemicalxyz", tracer)

    assert identity.status == "not_found"
    assert identity.smiles is None
    assert flags[-1].severity == "caution"
    assert [e.status for e in tracer.entries] == ["ok", "not_found"]


@respx.mock
async def test_pubchem_outage_degrades_to_caution_not_failure():
    mock_dsstox("62-75-9", fixture("toxindex/identity_ndma.json"))
    respx.get(pubchem_url("name", "62-75-9")).mock(side_effect=httpx.ConnectTimeout("timeout"))

    identity, flags = await resolve_identity("62-75-9", Tracer())

    assert identity.status == "resolved"
    assert severities(flags) == [("R1", "caution")]
    assert "Independent identity check unavailable" in flags[0].message


@respx.mock
async def test_toxindex_rate_limit_is_flagged_and_identity_falls_back_to_pubchem():
    respx.post(IDENTITY_TOOL).mock(return_value=httpx.Response(429, json={"error": "slow down"}))
    respx.get(pubchem_url("name", "62-75-9")).mock(
        return_value=httpx.Response(200, json=fixture("pubchem/name_62-75-9.json")))
    tracer = Tracer()

    identity, flags = await resolve_identity("62-75-9", tracer)

    assert tracer.entries[0].status == "rate_limited"
    assert identity.status == "resolved"
    assert identity.in_dsstox is False
    assert "DSSTox lookup via ToxIndex failed" in flags[0].message


@pytest.mark.parametrize("text", ["", "   ", "62-75-8"])
async def test_invalid_input_is_rejected_before_any_lookup(text):
    with pytest.raises(InvalidInput):
        await resolve_identity(text, Tracer())
