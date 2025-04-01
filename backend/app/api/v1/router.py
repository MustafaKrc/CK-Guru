from fastapi import APIRouter
from app.api.v1.endpoints import repositories, tasks

api_router = APIRouter()

# Include routers from endpoint files
api_router.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"]) # Add tasks router
# Add other endpoint routers here later (datasets, models, etc.)
# api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])