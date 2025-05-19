// frontend/types/api/ml-model.ts
import { ModelTypeEnum } from "./enums"; // Assuming enums.ts is created or ModelTypeEnum is imported elsewhere
import { DatasetRead } from "./dataset"; 
import { TrainingJobRead } from "./training-job";
import { HPSearchJobRead } from "./hp-search-job"; 

export interface MLModelRead {
  id: number;
  name: string;
  version: number;
  model_type: ModelTypeEnum;
  description?: string | null;
  hyperparameters?: Record<string, any> | null;
  performance_metrics?: Record<string, any> | null;
  dataset_id?: number | null;
  s3_artifact_path?: string | null;
  training_job_id?: number | null;
  hp_search_job_id?: number | null;
  
  // Add related objects
  dataset?: DatasetRead | null;
  training_job?: TrainingJobRead | null;
  hp_search_job?: HPSearchJobRead | null;
  
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

export interface PaginatedMLModelRead {
  items: MLModelRead[];
  total: number;
  skip: number;
  limit: number;
}

// Add Create/Update payloads if forms for these are built later
// export interface MLModelCreatePayload { ... }
// export interface MLModelUpdatePayload { ... }