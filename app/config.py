from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./simulations.db"
    DEFAULT_MODEL_ID: str = "mistral.mistral-large-2402-v1:0"
    MAX_CONCURRENT_AGENTS: int = 5
    AWS_DEFAULT_REGION: str = "us-west-2"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_prefix": "SSE_"}


settings = Settings()
