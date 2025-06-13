// frontend/types/api/training-job.ts
import { JobStatusEnum, ModelTypeEnum } from "./enums";
import { MLModelRead } from "./ml-model";
import { DatasetRead } from "./dataset"; // Import DatasetRead

// Config for a specific training run
export interface TrainingRunConfig {
  model_name: string;
  model_type: ModelTypeEnum;
  hyperparameters: Record<string, any>;
  feature_columns: string[];
  target_column: string;
  random_seed?: number | null;
  eval_test_split_size?: number | null;
}

export interface TrainingJobBase {
    dataset_id: number;
    config: TrainingRunConfig;
}

// Payload for creating a training job (sent to POST /ml/train)
export interface TrainingJobCreatePayload {
  dataset_id: number;
  training_job_name: string; 
  training_job_description?: string | null;
  config: TrainingRunConfig;
}

export interface TrainingJobRead extends TrainingJobBase {
  id: number;
  dataset?: DatasetRead | null; 
  celery_task_id?: string | null;
  status: JobStatusEnum;
  status_message?: string | null;
  ml_model_id?: number | null;
  ml_model?: MLModelRead | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingJobSubmitResponse {
    job_id: number;
    celery_task_id: string;
    message: string;
}

export interface PaginatedTrainingJobRead {
  items: TrainingJobRead[];
  total: number;
}