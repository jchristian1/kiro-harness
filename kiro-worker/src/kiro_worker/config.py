from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./kiro_worker.db"
    WORKSPACE_SAFE_ROOT: str = "/tmp/kiro-worker/workspaces"
    KIRO_CLI_PATH: str = "kiro-cli"
    KIRO_DEFAULT_AGENT: str = "repo-engineer"
    KIRO_CLI_TIMEOUT: int = 300
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 4000


settings = Settings()
