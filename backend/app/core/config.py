# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
# Import necessary types for validation
from pydantic import PostgresDsn, AmqpDsn, RedisDsn, AnyHttpUrl, Field, SecretStr
from typing import Any, Dict, List, Optional # Import Optional if RESULT_BACKEND might not be set
from pathlib import Path

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
logger.info(f"Object Storage Type: {settings.OBJECT_STORAGE_TYPE}")
logger.info(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
logger.info(f"S3 Endpoint URL: {settings.S3_ENDPOINT_URL or 'Default (AWS)'}")