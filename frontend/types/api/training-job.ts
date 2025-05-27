// frontend/types/api/training-job.ts
import { JobStatusEnum, ModelTypeEnum } from "./enums";
import { MLModelRead } from "./ml-model";

export interface TrainingConfig {
  model_name: string;
  model_type: ModelTypeEnum;
  hyperparameters: Record<string, any>; // User-configured hyperparameters
  feature_columns: string[]; // Selected features for training
  target_column: string; // Selected target column for training
  random_seed?: number | null;
  eval_test_split_size?: number | null;
  // Potentially add other config options like cross-validation strategy here
}

export interface TrainingJobRead {
  id: number;
  dataset_id: number;
  config: TrainingConfig;
  celery_task_id?: string | null;
  status: JobStatusEnum;
  status_message?: string | null;
  ml_model_id?: number | null;
  ml_model?: MLModelRead | null; // Nested model details
  started_at?: string | null; // ISO datetime string
  completed_at?: string | null; // ISO datetime string
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

// Payload for creating a training job
export interface TrainingJobCreatePayload {
  dataset_id: number;
  // The config now directly includes the job name and specific parameters
  // instead of nesting another 'config' object, for clarity in API call.
  // However, the backend DB model for TrainingJob still stores 'config' as a JSON.
  // The backend endpoint will take these flat and structure into its internal 'config'.
  training_job_name: string; // Name of the training job itself (for display/listing jobs)
  training_job_description?: string | null;
  model_base_name: string; // Base name for the MLModelDB record (versioning handled by backend)
  model_type: ModelTypeEnum;
  hyperparameters: Record<string, any>;
  feature_columns: string[];
  target_column: string;
  random_seed?: number | null;
  eval_test_split_size?: number | null;
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