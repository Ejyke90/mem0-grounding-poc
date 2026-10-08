from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 8000
    env: str = "development"

    # LLM (used by LangGraph agent)
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Mem0 configuration
    mem0_llm_model: str = "gpt-4o-mini"
    mem0_embedding_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
