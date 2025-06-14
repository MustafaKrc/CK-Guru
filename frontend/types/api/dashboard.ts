// frontend/types/api/dashboard.ts
export interface DatasetsByStatus {
  pending: number;
  generating: number;
  ready: number;
  failed: number;
}

export interface DashboardSummaryStats {
  total_repositories: number;
  total_datasets: number;
  datasets_by_status: DatasetsByStatus;
  total_ml_models: number;
  average_f1_score_ml_models?: number | null;
  active_ingestion_tasks: number;
  active_dataset_generation_tasks: number;
  active_ml_jobs: number;
}
