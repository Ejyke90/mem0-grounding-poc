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

    # Email ingestion: auth method ("auto", "oauth2", or "app_password")
    email_auth_method: str = "auto"

    # OAuth2 - Gmail API (Google Cloud Console -> OAuth client, type "Desktop")
    google_client_id: str = ""
    google_client_secret: str = ""
    # Optional: path to a downloaded client_secrets.json (overrides the env pair)
    google_client_secrets_file: str = ""

    # OAuth2 - Yahoo Mail (Yahoo Developer Network app, scopes: mail-r openid email)
    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = "http://localhost:8765/callback"

    # Where OAuth tokens are cached between runs (gitignored)
    oauth_token_dir: str = ".data/tokens"

    # App-password fallback (IMAP): still used if OAuth is not configured
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
