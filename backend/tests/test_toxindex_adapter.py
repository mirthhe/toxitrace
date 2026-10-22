import httpx
import pytest
import respx

from app.adapters import toxindex
from app.config import settings
from app.trace import Tracer
from tests.conftest import TOXINDEX_TOOLS, fixture

pytestmark = pytest.mark.anyio

NNV_SMILES = "O=NN1CC2CC(C1)c1cc3nccnc3cc12"


@respx.mock
async def test_success_is_traced_with_agent_headers():
    route = respx.post(f"{TOXINDEX_TOOLS}/toxjobs_predict").mock(
        return_value=httpx.Response(200, json=fixture("toxindex/amesformer_pfoa.json")))
    tracer = Tracer()

    ref, body = await toxindex.predict_ames("OC(=O)C(F)(F)F", tracer)

    assert ref == "toxindex-1"
    assert body["output"]["model"] == "AmesFormer-Pro"
    assert route.calls[0].request.headers["X-ToxIndex-Agent-Name"] == "ToxiTrace"
    assert tracer.entries[0].status == "ok"


@respx.mock
async def test_not_in_dsstox_422_raises_with_upstream_message():
    respx.post(f"{TOXINDEX_TOOLS}/tox_genotoxicity").mock(
        return_value=httpx.Response(422, json=fixture("toxindex/genotox_n-nitroso-varenicline.json")))
    tracer = Tracer()

    with pytest.raises(toxindex.ToxIndexError) as exc:
        await toxindex.genotoxicity(NNV_SMILES, tracer)

    assert exc.value.status == "not_found"
    assert "no substance in the EPA DSSTox registry" in str(exc.value)
    assert tracer.entries[0].ref == exc.value.ref


@respx.mock
async def test_timeout_raises_and_is_traced():
    respx.post(f"{TOXINDEX_TOOLS}/toxjobs_predict").mock(side_effect=httpx.ReadTimeout("slow"))
    tracer = Tracer()

    with pytest.raises(toxindex.ToxIndexError) as exc:
        await toxindex.predict_ames("CN(C)N=O", tracer)

    assert exc.value.status == "timeout"
    assert tracer.entries[0].status == "timeout"
    assert tracer.entries[0].response is None


@respx.mock
async def test_api_key_never_appears_in_trace(monkeypatch):
    monkeypatch.setattr(settings, "toxindex_api_key", "secret-test-key")
    respx.post(f"{TOXINDEX_TOOLS}/tox_chemical_identity").mock(
        return_value=httpx.Response(200, json=fixture("toxindex/identity_ndma.json")))
    tracer = Tracer()

    await toxindex.chemical_identity("62-75-9", tracer)

    assert "secret-test-key" not in tracer.entries[0].model_dump_json()
