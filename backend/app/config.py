from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-side configuration. Secrets live here only; never sent to the frontend or LLM."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    toxindex_api_key: str = ""
    toxindex_base_url: str = "https://platform.toxindex.com/v1"
    toxindex_timeout_seconds: float = 30.0

    llm_api_key: str = ""
    biobricks_token: str = ""


settings = Settings()
