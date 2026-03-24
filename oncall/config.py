from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://oncall:oncall@localhost/oncall"
    database_ssl: bool = False
    database_ssl_ca: str = ""
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_allowed_org: str = ""
    base_url: str = ""
    session_secret: str = ""

    @field_validator("session_secret", mode="before")
    @classmethod
    def _require_session_secret(cls, v: str) -> str:
        if not v or v == "change-me":
            raise ValueError(
                "SESSION_SECRET must be set to a random value. "
                "Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
