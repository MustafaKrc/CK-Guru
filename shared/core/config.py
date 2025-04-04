# worker/app/core/config.py
import os
from typing import Any, Dict, Optional # Use Optional for clarity, same as | None
from pathlib import Path

# Using pydantic-settings (recommended for Pydantic v2+)
# If using Pydantic v1, use `from pydantic import BaseSettings`
from pydantic import Field, AmqpDsn, PostgresDsn, RedisDsn, SecretStr  # For URL validation
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # --- Local Storage Path (Still needed for git clones) ---
    STORAGE_BASE_PATH: Path = Field(default=Path('/app/persistent_data'))

    # --- Object Storage Config ---
    OBJECT_STORAGE_TYPE: str = Field("s3", validation_alias="OBJECT_STORAGE_TYPE")
    S3_ENDPOINT_URL: Optional[str] = Field(None, validation_alias="S3_ENDPOINT_URL") # Required for MinIO/non-AWS
    S3_ACCESS_KEY_ID: Optional[str] = Field(None, validation_alias="S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: Optional[SecretStr] = Field(None, validation_alias="S3_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME: str = Field(..., validation_alias="S3_BUCKET_NAME") # Bucket must be configured
    S3_REGION: Optional[str] = Field(None, validation_alias="S3_REGION")
    S3_USE_SSL: bool = Field(True, validation_alias="S3_USE_SSL") # Default to True for safety

    # Helper property to construct storage options for fsspec/pandas
    @property
    def s3_storage_options(self) -> Dict[str, Any]:
        opts = {}
        # Only add credentials if they are set (allows IAM roles on AWS)
        if self.S3_ACCESS_KEY_ID:
            opts["key"] = self.S3_ACCESS_KEY_ID
        if self.S3_SECRET_ACCESS_KEY:
            opts["secret"] = self.S3_SECRET_ACCESS_KEY.get_secret_value()
        if self.S3_ENDPOINT_URL: # Crucial for MinIO
            opts["client_kwargs"] = {
                "endpoint_url": self.S3_ENDPOINT_URL,
                "region_name": self.S3_REGION # Pass region here too if needed
            }
            # Add use_ssl config for client_kwargs specifically for endpoint_url
            opts["use_ssl"] = self.S3_USE_SSL
        elif self.S3_REGION: # For standard AWS S3 if region needed
             # For AWS S3, region is often handled by boto implicitly or env vars
             # but can be set in client_kwargs if needed.
             # opts.setdefault("client_kwargs", {})["region_name"] = self.S3_REGION
             pass # s3fs usually picks up region from env or AWS config

        # Add other potential s3fs config like requester_pays etc. if needed
        return opts


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
logger.info(f"Object Storage Type: {settings.OBJECT_STORAGE_TYPE}")
logger.info(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
logger.info(f"S3 Endpoint URL: {settings.S3_ENDPOINT_URL or 'Default (AWS)'}")
if settings.GITHUB_TOKEN:
    logger.info("GitHub Token: Loaded (Token value not logged)")
else:
    logger.warning("GitHub Token: Not configured. Issue tracking will be disabled.")