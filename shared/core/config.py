# shared/core/config.py
import os
import re
from typing import Any, Dict, Optional
from pathlib import Path

from pydantic import Field, AmqpDsn, PostgresDsn, RedisDsn, SecretStr, computed_field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging # Import logging here for use within the class

# Setup logger before class definition if needed for methods inside
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application Configuration Settings. Loads variables from environment variables
    and potentially a .env file.
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    # --- Celery Configuration ---
    CELERY_BROKER_URL: AmqpDsn = Field(..., validation_alias='CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND: Optional[str] = Field(None, validation_alias='CELERY_RESULT_BACKEND')

    # --- Database Configuration ---
    DATABASE_URL: PostgresDsn = Field(..., validation_alias='DATABASE_URL')

    # --- GitHub API ---
    GITHUB_TOKEN: Optional[str] = Field(None, validation_alias='GITHUB_TOKEN')
    GITHUB_WEBHOOK_SECRET: Optional[SecretStr] = Field(None, validation_alias='GITHUB_WEBHOOK_SECRET') # <-- ADDED

    # --- Local Storage Path ---
    STORAGE_BASE_PATH: Path = Field(default=Path('/app/persistent_data'))

    # --- Object Storage Config ---
    OBJECT_STORAGE_TYPE: str = Field("s3", validation_alias="OBJECT_STORAGE_TYPE")
    S3_ENDPOINT_URL: Optional[str] = Field(None, validation_alias="S3_ENDPOINT_URL")
    S3_ACCESS_KEY_ID: Optional[str] = Field(None, validation_alias="S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: Optional[SecretStr] = Field(None, validation_alias="S3_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME: str = Field(..., validation_alias="S3_BUCKET_NAME")
    S3_REGION: Optional[str] = Field(None, validation_alias="S3_REGION")
    S3_USE_SSL: bool = Field(True, validation_alias="S3_USE_SSL")

    @property
    def s3_storage_options(self) -> Dict[str, Any]:
        opts = {}
        if self.S3_ACCESS_KEY_ID:
            opts["key"] = self.S3_ACCESS_KEY_ID
        if self.S3_SECRET_ACCESS_KEY:
            opts["secret"] = self.S3_SECRET_ACCESS_KEY.get_secret_value()
        if self.S3_ENDPOINT_URL:
            opts["client_kwargs"] = {
                "endpoint_url": self.S3_ENDPOINT_URL,
                "region_name": self.S3_REGION
            }
            opts["use_ssl"] = self.S3_USE_SSL
        elif self.S3_REGION:
             pass # s3fs usually picks up region from env or AWS config

        return opts

    @computed_field(return_type=str)
    @property
    def OPTUNA_DB_URL(self) -> str:
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured.")

        db_url_str = str(self.DATABASE_URL)
        sync_db_url = re.sub(r'\+asyncpg', '+psycopg2', db_url_str)
        if '+psycopg2' not in sync_db_url and sync_db_url.startswith('postgresql://'):
             sync_db_url = sync_db_url.replace('postgresql://', 'postgresql+psycopg2://')

        if not sync_db_url.startswith('postgresql+psycopg2://'):
             logger.warning(f"Could not reliably convert DATABASE_URL ('{db_url_str}') to Optuna sync URL. Using original.")
             return db_url_str

        return sync_db_url

    # --- Other Settings ---
    LOG_LEVEL: str = Field("INFO", validation_alias='LOG_LEVEL')
    # Define a default model ID to use for webhook inference if not configured elsewhere
    DEFAULT_WEBHOOK_MODEL_ID: int = Field(1, validation_alias='DEFAULT_WEBHOOK_MODEL_ID')


# Create a single, reusable settings instance
settings = Settings()

# --- Basic Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__) # Re-acquire logger after basicConfig
logger.info("Application settings loaded.")
# Log important settings (avoid logging secrets)
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Result Backend: {'Configured' if settings.CELERY_RESULT_BACKEND else 'Not Configured'}")
logger.info(f"Database URL: {'Configured' if settings.DATABASE_URL else 'Not Configured'}")
logger.info(f"Object Storage Type: {settings.OBJECT_STORAGE_TYPE}")
logger.info(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
logger.info(f"S3 Endpoint URL: {settings.S3_ENDPOINT_URL or 'Default (AWS)'}")
logger.info(f"Optuna DB URL: {settings.OPTUNA_DB_URL}")
if settings.GITHUB_TOKEN: logger.info("GitHub Token: Loaded")
else: logger.warning("GitHub Token: Not configured.")
if settings.GITHUB_WEBHOOK_SECRET: logger.info("GitHub Webhook Secret: Loaded")
else: logger.warning("GitHub Webhook Secret: Not configured. Webhook verification disabled.")
logger.info(f"Default Webhook Model ID: {settings.DEFAULT_WEBHOOK_MODEL_ID}")