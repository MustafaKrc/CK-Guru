// frontend/types/api/ml-model.ts
import { ModelTypeEnum } from "./enums";
import { DatasetRead } from "./dataset";
import { TrainingJobRead } from "./training-job";
import { HPSearchJobRead } from "./hp-search-job";
import { HyperparameterDefinition } from "@/types/jobs";

export interface MLModelRead {
  id: number;
  name: string;
  version: number;
  model_type: ModelTypeEnum;
  description?: string | null;
  hyperparameters?: Record<string, any> | null; // Actual HPs used by this *trained* model instance
  performance_metrics?: Record<string, any> | null;
  dataset_id?: number | null;
  s3_artifact_path?: string | null;
  training_job_id?: number | null;
  hp_search_job_id?: number | null;
  
  // Schema for *configuring* this model type (for new training jobs)
  // This is the crucial part for dynamic HP forms.
  // Backend should provide this when fetching model details or perhaps a separate endpoint for "model type capabilities".
  hyperparameter_schema?: HyperparameterDefinition[] | null; 

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