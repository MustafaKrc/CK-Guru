# backend/app/services/dashboard_service.py
import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models.dataset import Dataset, DatasetStatusEnum
from shared.db.models.hp_search_job import (
    HyperparameterSearchJob,
    JobStatusEnum as HPSearchJobStatusEnum,
)
from shared.db.models.inference_job import (
    InferenceJob,
    JobStatusEnum as InferenceJobStatusEnum,
)
from shared.db.models.ml_model import MLModel
from shared.db.models.repository import Repository
from shared.db.models.training_job import (
    TrainingJob,
    JobStatusEnum as TrainingJobStatusEnum,
)
from shared.schemas.dashboard import DashboardSummaryStats, DatasetsByStatus

logger = logging.getLogger(__name__)


class DashboardService:
    async def get_summary_stats(self, db: AsyncSession) -> DashboardSummaryStats:
        # Total Repositories
        repo_count_result = await db.execute(select(func.count(Repository.id)))
        total_repositories = repo_count_result.scalar_one_or_none() or 0

        # Total Datasets
        dataset_count_result = await db.execute(select(func.count(Dataset.id)))
        total_datasets = dataset_count_result.scalar_one_or_none() or 0

        # Datasets by Status
        datasets_status_raw = {status.value: 0 for status in DatasetStatusEnum}
        status_results_query = select(Dataset.status, func.count(Dataset.id)).group_by(
            Dataset.status
        )
        status_results = await db.execute(status_results_query)
        for status_enum_member, count in status_results.all():
            datasets_status_raw[status_enum_member.value] = count
        datasets_by_status_obj = DatasetsByStatus(**datasets_status_raw)

        # Total ML Models
        model_count_result = await db.execute(select(func.count(MLModel.id)))
        total_ml_models = model_count_result.scalar_one_or_none() or 0

        # Average F1 Score
        average_f1_score: Optional[float] = None
        f1_scores: list[float] = []
        metrics_query = select(MLModel.performance_metrics).where(
            MLModel.performance_metrics.is_not(None)
        )
        models_metrics_results = await db.execute(metrics_query)
        for metrics_dict in models_metrics_results.scalars().all():
            if isinstance(metrics_dict, dict):
                f1_value = metrics_dict.get("f1_weighted")
                if isinstance(f1_value, (int, float)):
                    f1_scores.append(float(f1_value))
                elif f1_value is not None:
                    logger.warning(
                        f"Non-numeric f1_weighted value encountered: {f1_value}"
                    )
        if f1_scores:
            average_f1_score = (
                sum(f1_scores) / len(f1_scores) if len(f1_scores) > 0 else 0.0
            )

        # Active ML Jobs
        active_training_jobs_res = await db.execute(
            select(func.count(TrainingJob.id)).where(
                TrainingJob.status.in_(
                    [
                        TrainingJobStatusEnum.PENDING,
                        TrainingJobStatusEnum.RUNNING,
                        #TrainingJobStatusEnum.STARTED,
                    ]
                )
            )
        )
        active_training_jobs = active_training_jobs_res.scalar_one_or_none() or 0

        active_hp_search_jobs_res = await db.execute(
            select(func.count(HyperparameterSearchJob.id)).where(
                HyperparameterSearchJob.status.in_(
                    [
                        HPSearchJobStatusEnum.PENDING,
                        HPSearchJobStatusEnum.RUNNING,
                        #HPSearchJobStatusEnum.STARTED,
                    ]
                )
            )
        )
        active_hp_search_jobs = active_hp_search_jobs_res.scalar_one_or_none() or 0

        active_inference_jobs_res = await db.execute(
            select(func.count(InferenceJob.id)).where(
                InferenceJob.status.in_(
                    [
                        InferenceJobStatusEnum.PENDING,
                        InferenceJobStatusEnum.RUNNING,
                        #InferenceJobStatusEnum.STARTED,
                    ]
                )
            )
        )
        active_inference_jobs = active_inference_jobs_res.scalar_one_or_none() or 0
        total_active_ml_jobs = (
            active_training_jobs + active_hp_search_jobs + active_inference_jobs
        )

        active_dataset_generation_tasks = (
            datasets_by_status_obj.generating + datasets_by_status_obj.pending
        )
        
        # Placeholder for active ingestion tasks.
        # A robust count requires tracking Celery task states for repository ingestion
        # or adding an 'ingestion_status' field to the Repository model.
        active_ingestion_tasks = 0 

        return DashboardSummaryStats(
            total_repositories=total_repositories,
            total_datasets=total_datasets,
            datasets_by_status=datasets_by_status_obj,
            total_ml_models=total_ml_models,
            average_f1_score_ml_models=average_f1_score,
            active_ingestion_tasks=active_ingestion_tasks,
            active_dataset_generation_tasks=active_dataset_generation_tasks,
            active_ml_jobs=total_active_ml_jobs,
        )

#TODO: singleton may not be the best pattern here, consider using dependency injection
dashboard_service = DashboardService()