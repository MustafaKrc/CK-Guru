// frontend/types/api/ml-model.ts
import { ModelTypeEnum } from "./enums";
import { DatasetRead } from "./dataset"; 
import { TrainingJobRead } from "./training-job";
import { HPSearchJobRead } from "./hp-search-job"; 
import { HyperparameterDefinition } from "@/types/jobs";

export interface ModelPerformanceMetrics {
  accuracy?: number;
  precision_weighted?: number;
  recall_weighted?: number;
  f1_weighted?: number;
  roc_auc?: number;        // Keep
  log_loss?: number;       // Keep
  training_time_seconds?: number; // Keep
  inference_latency_ms?: number; // Keep this, even if not populated by training
                                  // It might be populated by other means later.
  [key: string]: any; 
}

// Existing MLModelRead for trained models
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
  
  // This was where hyperparameter_schema was previously, but it makes more sense
  // for it to be part of an AvailableModelType definition, not every trained model instance.
  // If a trained model needs to show ITS schema, that's different.
  // For creating new jobs, we need the schema of the TYPE.

  dataset?: DatasetRead | null;
  training_job?: TrainingJobRead | null;
  hp_search_job?: HPSearchJobRead | null;
  
  created_at: string;
  updated_at: string;
}

export interface PaginatedMLModelRead {
  items: MLModelRead[];
  total: number;
  skip: number;
  limit: number;
}

// New type for representing an available model type for training
// This is what GET /ml/model-types should return
export interface AvailableModelType {
  type_name: ModelTypeEnum; // The enum value, e.g., "sklearn_randomforest"
  display_name: string;    // User-friendly name, e.g., "Scikit-learn Random Forest"
  description?: string;
  hyperparameter_schema: HyperparameterDefinition[]; // Crucial for dynamic forms
}