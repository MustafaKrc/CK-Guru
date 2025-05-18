// frontend/types/api/ml_model.ts
import { ModelTypeEnum } from "./enums"; // Assuming enums.ts is created or ModelTypeEnum is imported elsewhere

export interface MLModelRead {
  id: number;
  name: string;
  version: number;
  model_type: ModelTypeEnum; // Use the enum
  description?: string | null;
  hyperparameters?: Record<string, any> | null;
  performance_metrics?: Record<string, any> | null;
  dataset_id?: number | null;
  s3_artifact_path?: string | null;
  training_job_id?: number | null;
  hp_search_job_id?: number | null;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

// Add Create/Update payloads if forms for these are built later
// export interface MLModelCreatePayload { ... }
// export interface MLModelUpdatePayload { ... }