"""Offline mode: answer external API calls from recorded real responses instead of the network.

Enabled with TOXITRACE_OFFLINE=true. Used for UI development and for reviewers without an
API key. Only the recorded demo inputs are available; anything else gets a clear "not
recorded" error instead of a guessed answer. The UI shows which mode is active.
"""

import json
from pathlib import Path
from urllib.parse import unquote

import httpx

RECORDINGS = Path(__file__).resolve().parents[1] / "recordings"

NNV_SMILES = "O=NN1CC2CC(C1)c1cc3nccnc3cc12"

# (tool, identifying argument) -> recording, for POST /v1/tools/{tool}
TOXINDEX = {
    ("tox_chemical_identity", "62-75-9"): "toxindex/identity_ndma.json",
    ("tox_chemical_identity", "335-67-1"): "toxindex/identity_pfoa.json",
    ("tox_chemical_identity", "N-nitroso-varenicline"):
        "toxindex/identity_n-nitroso-varenicline.json",
    ("tox_chemical_identity", NNV_SMILES): "toxindex/identity_n-nitroso-varenicline_smiles.json",
}

# (namespace, value) -> recording, for PubChem GET /compound/{namespace}/{value}/property/...
PUBCHEM = {
    ("name", "62-75-9"): "pubchem/name_62-75-9.json",
    ("name", "335-67-1"): "pubchem/name_335-67-1.json",
    ("name", "N-nitroso-varenicline"): "pubchem/name_nnv.json",
    ("inchikey", "PTBAEGOZXFWTJH-UHFFFAOYSA-N"): "pubchem/inchikey_nnv.json",
}

# Inputs the UI offers as one-click examples in offline mode.
DEMO_INPUTS = ["62-75-9", "335-67-1", NNV_SMILES]


def _recorded(path: str, request: httpx.Request) -> httpx.Response:
    body = json.loads((RECORDINGS / path).read_text())
    # ToxIndex signals "not in DSSTox" with 422 and an "error" body; replay that faithfully.
    status = 422 if isinstance(body, dict) and set(body) == {"error"} else 200
    return httpx.Response(status, json=body, request=request)


def _not_recorded(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        501,  # not 503: PubChem uses 503 for "busy", which the adapter reports as rate limiting
        json={"error": "Offline mode: no recorded response for this request. "
                       f"Recorded demo inputs: {', '.join(DEMO_INPUTS)}"},
        request=request,
    )


def _handle(request: httpx.Request) -> httpx.Response:
    path = unquote(request.url.path)
    if request.url.host == "platform.toxindex.com" and "/tools/" in path:
        tool = path.rsplit("/", 1)[-1]
        args = json.loads(request.content or b"{}")
        key = args.get("identifier") or args.get("smiles")
        if recording := TOXINDEX.get((tool, key)):
            return _recorded(recording, request)
    if request.url.host == "pubchem.ncbi.nlm.nih.gov":
        parts = path.split("/")  # /rest/pug/compound/{namespace}/{value}/property/...
        if len(parts) > 5 and (recording := PUBCHEM.get((parts[4], parts[5]))):
            return _recorded(recording, request)
    return _not_recorded(request)


def transport() -> httpx.MockTransport:
    return httpx.MockTransport(_handle)
