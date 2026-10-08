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


settings = Settings()
