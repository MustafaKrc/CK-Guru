# worker/app/core/config.py
import os
from pathlib import Path
from typing import Optional # Use Optional for clarity, same as | None

# Using pydantic-settings (recommended for Pydantic v2+)
# If using Pydantic v1, use `from pydantic import BaseSettings`
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AmqpDsn, PostgresDsn, RedisDsn  # For URL validation

class Settings(BaseSettings):
    """
    Worker Configuration Settings. Loads variables from environment variables
    and potentially a .env file.
    """
    # Configure Pydantic settings
    # For pydantic v1:
    # class Config:
    #     env_file = '.env'
    #     env_file_encoding = 'utf-8'
    #     case_sensitive = True # Match env var case exactly
    # For pydantic v2+ (using pydantic-settings):
    model_config = SettingsConfigDict(
        env_file='.env',          # Load .env file if present
        env_file_encoding='utf-8',
        case_sensitive=True,      # Match env var case exactly
        extra='ignore'            # Ignore extra fields not defined here
    )

    # --- Celery Configuration ---
    # Broker URL is essential for receiving tasks
    # Example: amqp://guest:guest@ckguru_broker:5672//
    CELERY_BROKER_URL: AmqpDsn = Field(..., validation_alias='CELERY_BROKER_URL')

    # Result Backend URL (Optional for now, as requested)
    # If set (e.g., redis://ckguru_redis:6379/0 or db+postgresql+asyncpg://...),
    # Celery will store task status and results.
    # If None, status tracking via backend API (GET /tasks/{id}) will NOT work.
    CELERY_RESULT_BACKEND: Optional[str] = Field(None, validation_alias='CELERY_RESULT_BACKEND')

    # --- Database Configuration (Optional but recommended) ---
    # Worker tasks might need to update status or read related data.
    # Example: postgresql+asyncpg://user:password@ckguru_db:5432/mydatabase
    DATABASE_URL: PostgresDsn = Field(..., validation_alias='DATABASE_URL')

    # --- GitHub API --- 
    GITHUB_TOKEN: Optional[str] = Field(None, validation_alias='GITHUB_TOKEN')

    # --- Storage Configuration ---
    # Base path where the worker will store cloned repos (temp) and datasets
    # This path MUST be accessible within the worker container AND map to
    # a persistent volume if data needs to survive container restarts.
    # The default assumes '/app/persistent_data' inside the container.
    STORAGE_BASE_PATH: Path = Field(
        default=Path('/app/persistent_data'),
        validation_alias='STORAGE_BASE_PATH'
    )

    # --- Other Worker Settings ---
    # Example: Logging level
    LOG_LEVEL: str = Field("INFO", validation_alias='LOG_LEVEL')


# Create a single, reusable settings instance
settings = Settings()


# --- Optional: Basic Logging Setup ---
import logging
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)
logger.info("Worker settings loaded.")
logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Result Backend: {'Configured' if settings.CELERY_RESULT_BACKEND else 'Not Configured'}")
logger.info(f"Database URL: {'Configured' if settings.DATABASE_URL else 'Not Configured'}")
logger.info(f"Storage Path: {settings.STORAGE_BASE_PATH}")
if settings.GITHUB_TOKEN:
    logger.info("GitHub Token: Loaded (Token value not logged)")
else:
    logger.warning("GitHub Token: Not configured. Issue tracking will be disabled.")