from fastapi import APIRouter
from app.api.v1.endpoints import repositories, tasks, datasets, bot_patterns, ml_jobs, webhooks

api_router = APIRouter()

# Include routers from endpoint files
api_router.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"]) # Add tasks router


# Datasets endpoints (includes /datasets/available-cleaning-rules)
api_router.include_router(datasets.router, prefix="", tags=["Datasets"]) # Use prefix="" as paths are defined with /datasets already

# Bot Patterns endpoints (global and repo-specific might be defined within)
# If bot_patterns.py defines both /bot-patterns and /repositories/{id}/bot-patterns:
api_router.include_router(bot_patterns.router, prefix="", tags=["Bot Patterns"])
# Alternatively, if they were split:
# api_router.include_router(global_bot_patterns.router, prefix="/bot-patterns", tags=["Global Bot Patterns"])
# api_router.include_router(repo_bot_patterns.router, prefix="/repositories", tags=["Repository Bot Patterns"])

api_router.include_router(ml_jobs.router, prefix="/ml", tags=["ML Jobs & Models"])

api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])