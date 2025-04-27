# backend/app/api/v1/endpoints/webhooks.py
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

# Import Schemas, Config, DB Session, CRUD, Services
from shared import schemas
from shared.core.config import settings
from shared.db_session import get_async_db_session
from app import crud
from app.services.inference_orchestrator import InferenceOrchestrator

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

# --- Dependency for Signature Verification ---
async def verify_github_signature(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None) # Header can be missing
):
    """Dependency to verify the GitHub webhook signature."""
    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not configured. Skipping signature verification.")
        # In a production environment, you might want to raise an error here
        # raise HTTPException(status_code=500, detail="Webhook secret not configured on server.")
        return # Allow request if secret is not set on our side

    if not x_hub_signature_256:
        logger.error("Webhook request missing X-Hub-Signature-256 header.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature header.")

    try:
        # Read the raw body - crucial for signature verification
        # This needs to be done before FastAPI parses it into JSON
        body = await request.body()

        # Calculate expected signature
        secret = settings.GITHUB_WEBHOOK_SECRET.get_secret_value().encode('utf-8')
        hmac_obj = hmac.new(secret, msg=body, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hmac_obj.hexdigest()

        # Compare signatures securely
        if not hmac.compare_digest(expected_signature, x_hub_signature_256):
            logger.error(f"Webhook signature mismatch. Expected: {expected_signature}, Received: {x_hub_signature_256}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature.")

        logger.debug("GitHub webhook signature verified successfully.")
        # Store the raw body in request state if needed by endpoint (optional)
        # request.state.raw_body = body

    except HTTPException:
         raise # Re-raise HTTP exceptions
    except Exception as e:
         logger.error(f"Error during webhook signature verification: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error verifying signature.")


# --- Webhook Endpoint ---
@router.post(
    "/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Handle GitHub Webhooks (Push Events)",
    description="Receives push events from GitHub, verifies signature, and triggers inference pipeline.",
    dependencies=[Depends(verify_github_signature)] # Apply signature verification
)
async def handle_github_webhook(
    request: Request, # Need request object to get headers/body
    payload: Dict[str, Any], # FastAPI automatically parses JSON body
    background_tasks: BackgroundTasks, # Use background tasks for DB/Celery calls
    x_github_event: str = Header(...), # Require event header
    db: AsyncSession = Depends(get_async_db_session),
):
    """Handles incoming GitHub webhook events."""
    logger.info(f"Received GitHub webhook. Event: '{x_github_event}'")

    # --- Handle only 'push' events for now ---
    if x_github_event != 'push':
        logger.info(f"Ignoring non-push event: '{x_github_event}'")
        return {"message": f"Event '{x_github_event}' ignored."}

    # --- Parse Push Payload ---
    try:
        # Use Pydantic model for basic validation (optional but good)
        # push_data = schemas.GitHubPushPayload.model_validate(payload)
        # Or access dict directly
        repo_info = payload.get("repository", {})
        repo_url = repo_info.get("html_url")
        commit_hash = payload.get("after") # 'after' contains the latest commit hash in the push

        if not repo_url or not commit_hash or commit_hash == '0000000000000000000000000000000000000000':
            logger.warning(f"Ignoring push event: Missing repo URL or commit hash. URL='{repo_url}', Commit='{commit_hash}'")
            return {"message": "Push event ignored (missing data or branch deletion)."}

        logger.info(f"Processing push event for repo: {repo_url}, commit: {commit_hash}")

    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}", exc_info=True)
        # Return 400 Bad Request if payload is malformed
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload format.")

    # --- Async Task Triggering ---
    # Define the function to run in the background
    async def run_inference_trigger(repo_url: str, commit_hash: str):
        async with get_async_db_session() as async_db: # Get new session for background task
            try:
                # 1. Lookup Repository ID
                repo = await crud.crud_repository.get_repository_by_git_url(async_db, git_url=repo_url)
                if not repo:
                    logger.error(f"Webhook: Repository with URL '{repo_url}' not found in database.")
                    # Don't raise HTTPException here, just log error
                    return # Stop processing if repo not managed

                repo_id = repo.id

                # 2. Determine ML Model ID (Using default from settings for now)
                # TODO: Implement more sophisticated model selection logic if needed
                ml_model_id = settings.DEFAULT_WEBHOOK_MODEL_ID
                logger.info(f"Webhook: Using default model ID {ml_model_id} for repo {repo_id}")
                # Optionally add a DB check for the default model ID here

                # 3. Trigger Pipeline
                orchestrator = InferenceOrchestrator()
                await orchestrator.trigger_inference_pipeline(
                    db=async_db,
                    repo_id=repo_id,
                    commit_hash=commit_hash,
                    ml_model_id=ml_model_id,
                    trigger_source="webhook"
                )
                logger.info(f"Webhook: Successfully queued inference pipeline for repo {repo_id}, commit {commit_hash[:7]}")

            except Exception as bg_e:
                # Log any error during the background processing
                logger.error(f"Webhook background task failed for repo {repo_url}, commit {commit_hash}: {bg_e}", exc_info=True)
                # Note: We typically don't return errors to GitHub from the background task

    # Add the trigger function to background tasks
    background_tasks.add_task(run_inference_trigger, repo_url, commit_hash)

    # Return 202 Accepted immediately
    return {"message": "Webhook received and inference process initiated."}