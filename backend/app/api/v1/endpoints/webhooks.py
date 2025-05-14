# backend/app/api/v1/endpoints/webhooks.py
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

# Import Schemas, Config, DB Session, CRUD, Services
from shared.core.config import settings
from shared.db_session import get_async_db_session

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()


# --- Dependency for Signature Verification ---
async def verify_github_signature(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),  # Header can be missing
):
    """Dependency to verify the GitHub webhook signature."""
    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.warning(
            "GITHUB_WEBHOOK_SECRET not configured. Skipping signature verification."
        )
        # In a production environment, you might want to raise an error here
        # raise HTTPException(status_code=500, detail="Webhook secret not configured on server.")
        return  # Allow request if secret is not set on our side

    if not x_hub_signature_256:
        logger.error("Webhook request missing X-Hub-Signature-256 header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature header."
        )

    try:
        # Read the raw body - crucial for signature verification
        # This needs to be done before FastAPI parses it into JSON
        body = await request.body()

        # Calculate expected signature
        secret = settings.GITHUB_WEBHOOK_SECRET.get_secret_value().encode("utf-8")
        hmac_obj = hmac.new(secret, msg=body, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hmac_obj.hexdigest()

        # Compare signatures securely
        if not hmac.compare_digest(expected_signature, x_hub_signature_256):
            logger.error(
                f"Webhook signature mismatch. Expected: {expected_signature}, Received: {x_hub_signature_256}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature.",
            )

        logger.debug("GitHub webhook signature verified successfully.")
        # Store the raw body in request state if needed by endpoint (optional)
        # request.state.raw_body = body

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error during webhook signature verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying signature.",
        )


# --- Webhook Endpoint ---
@router.post(
    "/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Handle GitHub Webhooks (Push Events)",
    description="Receives push events from GitHub, verifies signature, and triggers inference pipeline.",
    dependencies=[Depends(verify_github_signature)],  # Apply signature verification
)
async def handle_github_webhook(
    request: Request,  # Need request object to get headers/body
    payload: Dict[str, Any],  # FastAPI automatically parses JSON body
    background_tasks: BackgroundTasks,  # Use background tasks for DB/Celery calls
    x_github_event: str = Header(...),  # Require event header
    db: AsyncSession = Depends(get_async_db_session),
):
    """Handles incoming GitHub webhook events."""

    return {
        "message": "Not implemented.",
    }
