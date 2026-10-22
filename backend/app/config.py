from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Server-side configuration. Secrets live here only; never sent to the frontend or LLM."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    toxindex_api_key: str = ""
    toxindex_base_url: str = "https://platform.toxindex.com/v1"
    toxindex_timeout_seconds: float = 30.0

    llm_api_key: str = ""

    # Serve external API calls from backend/recordings/ instead of the network (app/replay.py).
    toxitrace_offline: bool = False

    # Reference data fetched by `python -m app.reference_data`; gitignored.
    data_dir: Path = REPO_ROOT / "data"


settings = Settings()
