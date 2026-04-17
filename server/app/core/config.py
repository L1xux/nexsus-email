from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database (PostgreSQL for production)
    database_url: str = ""

    # For backward compatibility, also accept individual PostgreSQL settings
    postgres_host: str = ""
    postgres_port: int = 5432
    postgres_database: str = ""
    postgres_user: str = ""
    postgres_password: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Build database_url from individual settings if not provided
        if not self.database_url and self.postgres_host:
            self.database_url = f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for migrations."""
        if "+asyncpg" in self.database_url:
            return self.database_url.replace("+asyncpg", "")
        return self.database_url

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

    # OpenAI (for AI Classification)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # HuggingFace (for free embeddings)
    hf_token: str = ""

    # Qdrant (Vector DB for RAG)
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "nexusmail_feedback"

    # Legacy Qdrant settings (for backward compatibility)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis (optional)
    redis_url: str = ""

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
