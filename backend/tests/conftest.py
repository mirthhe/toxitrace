import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "recordings"
TOXINDEX_TOOLS = "https://platform.toxindex.com/v1/tools"
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PUBCHEM_PROPS = "property/MolecularFormula,SMILES,InChIKey,IUPACName/JSON"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch, request):
    """Unit tests never call the Claude API, even if a key is configured locally.

    Tests that exercise the narrative mock `narrative._call_llm` instead.
    """
    if "live" not in request.keywords:
        from app.config import settings
        monkeypatch.setattr(settings, "llm_api_key", "")


def fixture(path: str) -> dict:
    """Recorded real responses (ToxIndex captures from 2026-10-21, PubChem from 2026-10-22)."""
    return json.loads((FIXTURES / path).read_text())


def pubchem_url(namespace: str, value: str) -> str:
    return f"{PUBCHEM}/{namespace}/{value}/{PUBCHEM_PROPS}"
