"""Contract tests against the live ToxIndex and PubChem APIs.

Opt-in only: `uv run pytest -m live`. One run makes 3 ToxIndex calls (one identity lookup per
demo chemical) and 3 PubChem calls. They check that the fields and behaviour ToxiTrace relies
on still hold, not exact model values. The unit tests cover the same logic on recorded
responses; these detect when the live API has drifted away from those recordings.
"""

import pytest

from app.adapters import toxindex
from app.config import settings
from app.identity import resolve_identity
from app.trace import Tracer

pytestmark = [
    pytest.mark.live,
    pytest.mark.anyio,
    pytest.mark.skipif(not settings.toxindex_api_key, reason="TOXINDEX_API_KEY not set"),
]


@pytest.fixture(autouse=True)
def label_calls_as_tests(monkeypatch):
    """Make contract-test traffic distinguishable from app traffic in ToxIndex's logs."""
    monkeypatch.setitem(toxindex.AGENT_HEADERS, "X-ToxIndex-Agent-Name",
                        "ToxiTrace (live contract test)")


async def test_ndma_resolves_to_known_dtxsid_and_pubchem_agrees():
    identity, flags = await resolve_identity("62-75-9", Tracer())

    assert identity.status == "resolved"
    assert identity.dtxsid == "DTXSID7021029"
    assert identity.inchikey == "UMFJAHHVKNCGLG-UHFFFAOYSA-N"
    assert all(f.severity != "conflict" for f in flags)


async def test_pfoa_resolves_to_free_acid():
    identity, _ = await resolve_identity("335-67-1", Tracer())

    assert identity.status == "resolved"
    assert identity.dtxsid == "DTXSID8031865"
    assert identity.inchikey == "SNGREZUHAYWORS-UHFFFAOYSA-N"


async def test_n_nitroso_varenicline_still_absent_from_dsstox():
    """If this starts failing, DSSTox has added the substance: good news, but update the demo."""
    identity, _ = await resolve_identity("O=NN1CC2CC(C1)c1cc3nccnc3cc12", Tracer())

    assert identity.status == "resolved"
    assert identity.in_dsstox is False
    assert identity.pubchem_cid == 163880833
