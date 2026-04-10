from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    mariadb_host: str = "localhost"
    mariadb_port: int = 3306
    mariadb_database: str = "nexusmail"
    mariadb_user: str = "nexusmail"
    mariadb_password: str = "nexusmail"

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.mariadb_user}:{self.mariadb_password}@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_database}"

    # JWT
    jwt_secret_key: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/callback"
    gmail_pubsub_topic: str = ""
    gmail_webhook_verification_token: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "nexusmail_feedback"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    client_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
