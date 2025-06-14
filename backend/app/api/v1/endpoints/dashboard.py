# backend/app/api/v1/endpoints/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard_service import dashboard_service
from shared.db_session import get_async_db_session
from shared.schemas.dashboard import DashboardSummaryStats

router = APIRouter()


@router.get("/stats", response_model=DashboardSummaryStats)
async def get_dashboard_summary_stats_endpoint(
    db: AsyncSession = Depends(get_async_db_session),
):
    """
    Retrieve summary statistics for the dashboard.
    """
    stats = await dashboard_service.get_summary_stats(db)
    return stats
