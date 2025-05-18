// frontend/types/api/training-job.ts
import { JobStatusEnum, ModelTypeEnum } from "./enums"; // Assuming enums.ts
import { MLModelRead } from "./ml-model";

export interface TrainingConfig {
  model_name: string;
  model_type: ModelTypeEnum;
  hyperparameters: Record<string, any>;
  feature_columns: string[];
  target_column: string;
  random_seed?: number | null;
  eval_test_split_size?: number | null;
}

export interface TrainingJobRead {
  id: number;
  dataset_id: number;
  config: TrainingConfig;
  celery_task_id?: string | null;
  status: JobStatusEnum; // Use the enum
  status_message?: string | null;
  ml_model_id?: number | null;
  ml_model?: MLModelRead | null; // Nested model details
  started_at?: string | null; // ISO datetime string
  completed_at?: string | null; // ISO datetime string
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

// For creating a training job
export interface TrainingJobCreatePayload {
  dataset_id: number;
  config: TrainingConfig;
}

// For the API response when submitting a job
export interface TrainingJobSubmitResponse {
    job_id: number;
    celery_task_id: string;
    message: string;
}

export interface PaginatedTrainingJobRead {
  items: TrainingJobRead[];
  total: number;
}