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
    session_secret: str = "change-me"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
