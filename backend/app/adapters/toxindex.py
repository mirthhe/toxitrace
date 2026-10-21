"""ToxIndex adapter.

TODO(discovery gate, SPEC §2): fill in the real endpoint path, request body and response
fields after inspecting https://platform.toxindex.com/v1/openapi.json with an API key.
Do not guess paths or fields.
"""

import httpx

from app.config import settings


class ToxIndexError(Exception):
    """Raised for any upstream failure. Callers must never fabricate a prediction on error."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.toxindex_base_url,
        headers={"Authorization": f"Bearer {settings.toxindex_api_key}"},  # TODO: confirm auth scheme
        timeout=settings.toxindex_timeout_seconds,
    )


async def fetch_openapi_schema() -> dict:
    """Discovery helper: pull the live OpenAPI schema."""
    async with _client() as client:
        resp = await client.get("/v1/openapi.json")
        resp.raise_for_status()
        return resp.json()


async def predict(chemical_input: str) -> dict:
    """Call the chosen ToxIndex model endpoint and return the raw JSON response."""
    raise NotImplementedError("Choose the endpoint during the discovery gate")
