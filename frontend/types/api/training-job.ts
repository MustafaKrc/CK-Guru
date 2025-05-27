// frontend/types/api/training-job.ts
import { JobStatusEnum, ModelTypeEnum } from "./enums";
import { MLModelRead } from "./ml-model";

// Config for a specific training run
export interface TrainingRunConfig {
  // This is what TrainingJob.config in the DB will store.
  // It's a subset of what frontend's TrainingJobFormData holds,
  // focusing on what defines the model and its training process.
  model_name: string; // Base name for the MLModelDB record (e.g., "MyDataset_RF")
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
  config: TrainingRunConfig; // DB stores this structure in its JSON 'config' field
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

// Payload for creating a training job (sent to POST /ml/train)
export interface TrainingJobCreatePayload {
  dataset_id: number;
  // User-defined name & description for the TrainingJobDB record itself
  training_job_name: string; 
  training_job_description?: string | null;
  
  // Configuration for the actual model training process
  config: TrainingRunConfig;
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