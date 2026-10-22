"""ToxIndex adapter: every tool is called through POST /v1/tools/{name}.

Response shapes are documented in docs/discovery-notes.md. Errors are raised, never turned
into results: callers must not fabricate a prediction when a call fails.
"""

import time
from typing import Any

import httpx

from app import replay
from app.config import settings
from app.trace import Tracer

# Identify ToxiTrace in ToxIndex's logs (POST /tools/{name} accepts these headers).
AGENT_HEADERS = {
    "X-ToxIndex-Agent-Name": "ToxiTrace",
    "X-ToxIndex-Agent-Harness": "toxitrace-backend",
}


class ToxIndexError(Exception):
    """Raised for any upstream failure. Callers must never fabricate a prediction on error."""

    def __init__(self, message: str, ref: str, status: str):
        super().__init__(message)
        self.ref = ref
        self.status = status


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.toxindex_base_url,
        headers={"Authorization": f"Bearer {settings.toxindex_api_key}"},
        timeout=settings.toxindex_timeout_seconds,
        transport=replay.transport() if settings.toxitrace_offline else None,
    )


async def fetch_openapi_schema() -> dict:
    """Discovery helper: pull the live OpenAPI schema."""
    async with _client() as client:
        resp = await client.get("/openapi.json")
        resp.raise_for_status()
        return resp.json()


def _body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


async def call_tool(name: str, arguments: dict, tracer: Tracer) -> tuple[str, Any]:
    """Execute one tool and trace it. Returns (trace ref, parsed response body)."""
    start = time.perf_counter()

    def elapsed() -> int:
        return round((time.perf_counter() - start) * 1000)

    try:
        async with _client() as client:
            resp = await client.post(f"/tools/{name}", json=arguments, headers=AGENT_HEADERS)
    except httpx.TimeoutException:
        ref = tracer.record("toxindex", name, "timeout", arguments, duration_ms=elapsed(),
                            error="ToxIndex did not respond in time")
        raise ToxIndexError("ToxIndex did not respond in time", ref, "timeout")
    except httpx.HTTPError as exc:
        ref = tracer.record("toxindex", name, "error", arguments, duration_ms=elapsed(),
                            error=f"connection failed: {exc}")
        raise ToxIndexError(f"could not reach ToxIndex: {exc}", ref, "error")

    body = _body(resp)
    if resp.is_success:
        return tracer.record("toxindex", name, "ok", arguments, body, duration_ms=elapsed()), body

    message = body.get("error") if isinstance(body, dict) else None
    message = message or f"HTTP {resp.status_code}"
    status = {429: "rate_limited", 404: "not_found", 422: "not_found"}.get(resp.status_code, "error")
    ref = tracer.record("toxindex", name, status, arguments, body, message, elapsed())
    raise ToxIndexError(message, ref, status)


async def chemical_identity(identifier: str, tracer: Tracer) -> tuple[str, dict]:
    """tox_chemical_identity: up to 5 DSSTox matches plus "total"."""
    return await call_tool("tox_chemical_identity", {"identifier": identifier}, tracer)


async def predict_ames(smiles: str, tracer: Tracer) -> tuple[str, dict]:
    """AmesFormer-Pro via toxjobs_predict: {"output": {probability, mutagenic, threshold, ...}}."""
    return await call_tool("toxjobs_predict", {"tool": "amesformer", "smiles": smiles}, tracer)


async def genotoxicity(identifier: str, tracer: Tracer) -> tuple[str, dict]:
    """tox_genotoxicity: verdict plus findings labelled by method; 422 if not in DSSTox."""
    return await call_tool("tox_genotoxicity", {"identifier": identifier}, tracer)
