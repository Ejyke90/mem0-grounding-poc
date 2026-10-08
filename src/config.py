from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = 8000
    env: str = "development"

    # Ollama (local, free)
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"

    # Mem0 configuration (also uses Ollama)
    mem0_llm_model: str = "llama3.2"
    mem0_embedding_model: str = "nomic-embed-text"

    # Email ingestion (IMAP + app password, not your main account password)
    gmail_user: str = ""
    gmail_app_password: str = ""
    yahoo_user: str = ""
    yahoo_app_password: str = ""

    # Object storage (any S3-compatible free tier: Cloudflare R2, Backblaze B2, MinIO)
    object_storage_endpoint_url: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_bucket: str = ""
    object_storage_region: str = "auto"


settings = Settings()
