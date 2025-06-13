// frontend/types/api/dataset.ts
import { DatasetStatusEnum } from "./enums"; // Import from the local enums file
import { Repository } from "./repository";

// Mirrors CleaningRuleConfig from shared/schemas/dataset.py
export interface CleaningRuleConfig {
  name: string;
  enabled: boolean;
  params?: Record<string, any>; // Parameters specific to this rule
}

export interface FeatureSelectionConfig {
  name: string;
  params: Record<string, any>;
}

// This interface should mirror shared/schemas/dataset.py -> DatasetConfig
export interface DatasetConfig {
  feature_columns: string[];
  target_column: string;
  cleaning_rules: CleaningRuleConfig[]; // Use the exported CleaningRuleConfig
  feature_selection?: FeatureSelectionConfig | null;
}

// This interface should mirror shared/schemas/dataset.py -> DatasetRead
export interface DatasetRead {
  id: number;
  repository_id: number;
  repository?: Repository;
  name: string;
  description?: string | null;
  config: DatasetConfig;
  status: DatasetStatusEnum | string; // Allow string for robustness
  status_message?: string | null;
  storage_path?: string | null;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
  background_data_path?: string | null;
  num_rows?: number | null;
}

// Payload for creating a dataset, mirrors shared/schemas/dataset.py -> DatasetCreate
export interface DatasetCreatePayload {
    name: string;
    description?: string | null;
    config: DatasetConfig;
}

// Response when a dataset creation task is submitted, mirrors shared/schemas/dataset.py -> DatasetTaskResponse
export interface DatasetTaskResponse {
    dataset_id: number;
    task_id: string;
}

export interface PaginatedDatasetRead {
  items: DatasetRead[];
  total: number;
  skip?: number;
  limit?: number;
}