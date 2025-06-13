// frontend/types/api/hp-search-job.ts
import { JobStatusEnum, ModelTypeEnum, ObjectiveMetricEnum, SamplerTypeEnum, PrunerTypeEnum } from "./enums";
import { MLModelRead } from "./ml-model";
import { DatasetRead } from "./dataset"; // Import DatasetRead

export interface HPSuggestion {
  param_name: string;
  suggest_type: "float" | "int" | "categorical";
  low?: number | null;
  high?: number | null;
  step?: number | null;
  log?: boolean;
  choices?: any[] | null;
}

export interface OptunaConfig {
  n_trials: number;
  objective_metric: ObjectiveMetricEnum;
  sampler_type: SamplerTypeEnum;
  sampler_config?: Record<string, any> | null;
  pruner_type: PrunerTypeEnum;
  pruner_config?: Record<string, any> | null;
  continue_if_exists: boolean;
  hp_search_cv_folds?: number | null;
}

export interface HPSearchConfig {
  model_name: string;
  model_type: ModelTypeEnum;
  hp_space: HPSuggestion[];
  optuna_config: OptunaConfig;
  save_best_model: boolean;
  feature_columns: string[];
  target_column: string;
  random_seed?: number | null;
}

export interface HPSearchJobBase {
    dataset_id: number;
    optuna_study_name: string;
    config: HPSearchConfig;
}

// For creating an HP search job
export interface HPSearchJobCreatePayload {
    dataset_id: number;
    optuna_study_name: string;
    config: HPSearchConfig;
}

// For the API response when submitting an HP search job
export interface HPSearchJobSubmitResponse {
    job_id: number;
    celery_task_id: string;
    message: string;
}

export interface HPSearchJobRead extends HPSearchJobBase {
  id: number;
  dataset?: DatasetRead | null; // <-- Add this line
  celery_task_id?: string | null;
  status: JobStatusEnum;
  status_message?: string | null;
  best_trial_id?: number | null;
  best_params?: Record<string, any> | null;
  best_value?: number | null;
  best_ml_model_id?: number | null;
  best_ml_model?: MLModelRead | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedHPSearchJobRead {
  items: HPSearchJobRead[];
  total: number;
  skip?: number;
  limit?: number;
}