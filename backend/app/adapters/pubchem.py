"""PubChem PUG REST adapter: an identity source independent of ToxIndex/DSSTox.

Unlike ToxIndex, a PubChem failure is not fatal: identity can still rest on DSSTox alone,
and the missing cross-check is flagged instead.
"""

import time
from urllib.parse import quote

import httpx

from app import mode, replay
from app.schemas import Candidate
from app.trace import Tracer

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PROPERTIES = "MolecularFormula,SMILES,InChIKey,IUPACName"
TIMEOUT_SECONDS = 15


class PubChemMatch(Candidate):
    cid: int


async def _lookup(namespace: str, value: str, tracer: Tracer) -> tuple[str, list[PubChemMatch]]:
    url = f"{BASE_URL}/{namespace}/{quote(value, safe='')}/property/{PROPERTIES}/JSON"
    request = {"namespace": namespace, "value": value}
    start = time.perf_counter()
    try:
        transport = replay.transport() if mode.offline() else None
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
            resp = await client.get(url)
    except httpx.TimeoutException:
        ref = tracer.record("pubchem", f"lookup by {namespace}", "timeout", request,
                            error="PubChem did not respond in time")
        return ref, []
    except httpx.HTTPError as exc:
        ref = tracer.record("pubchem", f"lookup by {namespace}", "error", request,
                            error=f"connection failed: {exc}")
        return ref, []

    duration_ms = round((time.perf_counter() - start) * 1000)
    if resp.status_code == 404:
        ref = tracer.record("pubchem", f"lookup by {namespace}", "not_found", request,
                            resp.json(), duration_ms=duration_ms)
        return ref, []
    if not resp.is_success:
        status = "rate_limited" if resp.status_code == 503 else "error"
        ref = tracer.record("pubchem", f"lookup by {namespace}", status, request,
                            error=f"HTTP {resp.status_code}", duration_ms=duration_ms)
        return ref, []

    body = resp.json()
    ref = tracer.record("pubchem", f"lookup by {namespace}", "ok", request, body,
                        duration_ms=duration_ms)
    matches = [
        PubChemMatch(
            cid=p["CID"],
            name=p.get("IUPACName"),
            inchikey=p.get("InChIKey"),
            smiles=p.get("SMILES"),
            formula=p.get("MolecularFormula"),
        )
        for p in body.get("PropertyTable", {}).get("Properties", [])
    ]
    return ref, matches


async def by_name(name_or_cas: str, tracer: Tracer) -> tuple[str, list[PubChemMatch]]:
    """PubChem's name namespace also resolves CAS numbers (they are registered synonyms)."""
    return await _lookup("name", name_or_cas, tracer)


async def by_inchikey(key: str, tracer: Tracer) -> tuple[str, list[PubChemMatch]]:
    return await _lookup("inchikey", key, tracer)
