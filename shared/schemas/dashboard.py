# shared/schemas/dashboard.py
from typing import Optional

from pydantic import BaseModel


class DatasetsByStatus(BaseModel):
    pending: int = 0
    generating: int = 0
    ready: int = 0
    failed: int = 0


class DashboardSummaryStats(BaseModel):
    total_repositories: int
    total_datasets: int
    datasets_by_status: DatasetsByStatus
    total_ml_models: int
    average_f1_score_ml_models: Optional[float] = None
    active_ingestion_tasks: int 
    active_dataset_generation_tasks: int
    active_ml_jobs: int