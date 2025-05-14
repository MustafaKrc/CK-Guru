from fastapi import APIRouter

from app.api.v1.endpoints import (
    bot_patterns,
    datasets,
    ml_jobs,
    repositories,
    tasks,
    webhooks,
    xai,
)

api_router = APIRouter()

# Include routers from endpoint files
api_router.include_router(
    repositories.router, prefix="/repositories", tags=["Repositories"]
)
api_router.include_router(
    tasks.router, prefix="/tasks", tags=["Tasks"]
)  # Add tasks router


# Datasets endpoints (includes /datasets/available-cleaning-rules)
api_router.include_router(
    datasets.router, prefix="", tags=["Datasets"]
)  # Use prefix="" as paths are defined with /datasets already

# Bot Patterns endpoints (global and repo-specific might be defined within)
# If bot_patterns.py defines both /bot-patterns and /repositories/{id}/bot-patterns:
api_router.include_router(bot_patterns.router, prefix="", tags=["Bot Patterns"])

# ML Jobs (Training, HP Search), Models, Inference Triggering, XAI Triggering
api_router.include_router(
    ml_jobs.router, prefix="/ml", tags=["ML & Inference Jobs"]
)  # Consolidated tag

# XAI Results Reading
api_router.include_router(
    xai.router, prefix="/xai", tags=["XAI Explanations"]
)  # Endpoint for reading XAI results

# Webhooks
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
