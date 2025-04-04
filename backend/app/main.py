from fastapi import FastAPI

from app.api.v1.router import api_router

from shared.core.config import settings # Import settings if needed later for app config

# --- Metadata for OpenAPI Docs ---
description = """
JIT Software Defect Prediction API helps you predict bugs in your code changes. 🚀

You can:
*   **Register Git Repositories**
*   Create Datasets from repository history (coming soon)
*   Train Prediction Models (coming soon)
*   Configure CI/CD pipelines for inference (coming soon)
*   View Predictions and Insights (coming soon)
"""

app = FastAPI(
    title="JIT Defect Prediction API",
    description=description,
    version="0.1.0",
    # terms_of_service="http://example.com/terms/", # Optional
    # contact={ # Optional
    #     "name": "API Support",
    #     "url": "http://www.example.com/support",
    #     "email": "support@example.com",
    # },
    # license_info={ # Optional
    #     "name": "Apache 2.0",
    #     "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    # },
    openapi_url="/api/v1/openapi.json", # Standard location
    docs_url="/api/docs",              # Standard location for Swagger UI
    redoc_url="/api/redoc",            # Standard location for ReDoc
)

# Include the API router
app.include_router(api_router, prefix="/api/v1") # Add the /api/v1 prefix here

# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
async def read_root():
    """Basic health check endpoint."""
    return {"status": "ok", "message": "Welcome to JIT Defect Prediction API!"}

# --- Optional: Add Middleware (CORS, etc.) ---
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000"], # Adjust for your frontend URL
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# --- Optional: Add startup/shutdown events ---
# @app.on_event("startup")
# async def startup_event():
#     # Initialize database tables (alternative to alembic for simple cases)
#     # async with async_engine.begin() as conn:
#     #     await conn.run_sync(Base.metadata.create_all)
#     print("Application startup...")

# @app.on_event("shutdown")
# async def shutdown_event():
#     print("Application shutdown...")
#     await async_engine.dispose() # Clean up engine resources