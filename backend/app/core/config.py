# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
# Import necessary types for validation
from pydantic import PostgresDsn, AmqpDsn, RedisDsn, AnyHttpUrl
from typing import List, Optional # Import Optional if RESULT_BACKEND might not be set

class Settings(BaseSettings):
    # --- Database Configuration ---
    DATABASE_URL: PostgresDsn

    # --- Celery Configuration --- <<< ADD THESE LINES
    CELERY_BROKER_URL: AmqpDsn  # Use AmqpDsn for RabbitMQ URL validation
    # Make RESULT_BACKEND mandatory if the GET /tasks endpoint is essential
    CELERY_RESULT_BACKEND: RedisDsn # Use RedisDsn for Redis URL validation
    # Or use Optional if you want to allow running without it configured:
    # CELERY_RESULT_BACKEND: Optional[RedisDsn] = None

    # --- Optional Other Settings ---
    # API_V1_STR: str = "/api/v1"
    # PROJECT_NAME: str = "JIT Defect Predictor"
    # ALLOWED_HOSTS: List[str] = ["*"] # Be more specific in production

    # --- Pydantic Model Config ---
    model_config = SettingsConfigDict(
        env_file=".env",    # Load from .env file if present
        extra='ignore',     # Ignore extra env vars not defined above
        case_sensitive=True # Match env var names exactly
    )

# Instantiate settings (loads values from env/.env on import)
settings = Settings()

# --- Optional: Add logging to confirm loading ---
import logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
logger.info("Backend settings loaded.")
logger.info(f"Database URL: Loaded") # Avoid logging sensitive parts
logger.info(f"Celery Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Celery Result Backend: {settings.CELERY_RESULT_BACKEND}")