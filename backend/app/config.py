from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Server-side configuration. Secrets live here only; never sent to the frontend or LLM."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    toxindex_api_key: str = ""
    toxindex_base_url: str = "https://platform.toxindex.com/v1"
    toxindex_timeout_seconds: float = 30.0

    llm_api_key: str = ""

    # Serve external API calls from backend/recordings/ instead of the network (app/replay.py).
    toxitrace_offline: bool = False

    # Public deployment: with an access code set, requests are offline unless they carry the
    # code (header X-Access-Code); live analyses are capped per hour. See app/mode.py.
    demo_access_code: str = ""
    live_analyses_per_hour: int = 30

    # Reference data fetched by `python -m app.reference_data`; gitignored. Defaults to data/ at
    # the repository root, or backend/data/ when only that exists (as in a Vercel build).
    data_dir: Path = REPO_ROOT / "data" if not (BACKEND_ROOT / "data").exists() else BACKEND_ROOT / "data"
    # If no reference data is installed, download it on first use (e.g. serverless deploys).
    fetch_reference_data_on_demand: bool = False


settings = Settings()
