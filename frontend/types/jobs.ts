// frontend/types/jobs.ts

import { ModelTypeEnum } from "./api/enums"; // Assuming this is correctly defined in your enums
import { CleaningRuleConfig } from "./api/dataset"; // Import from dataset types

/**
 * Definition for a single hyperparameter, used to dynamically generate forms.
 * This structure should be provided by the backend when fetching model details.
 */
export interface HyperparameterDefinition {
  name: string;
  type: "integer" | "float" | "string" | "boolean" | "enum" | "text_choice";
  description?: string;
  default_value?: any; // Default value for the hyperparameter
  example_value?: any; // Example value (can be same as default or different)
  options?: Array<{ value: string | number; label: string }>; // For enum or text_choice
  range?: { min?: number; max?: number; step?: number }; // For numeric types
  required?: boolean;
}

/**
 * Represents the accumulated form data throughout the training job creation wizard.
 */
export interface TrainingJobFormData {
  // Step 1: Repository & Dataset
  repositoryId: number | null;
  repositoryName?: string; // For display purposes
  datasetId: number | null;
  datasetName?: string; // For display purposes
  datasetFeatureSpace: string[]; // Available features from the selected dataset
  datasetTargetColumn?: string | null; // Target column from dataset config (often fixed)

  // Step 2: Model Selection
  modelId: number | null;
  modelType: ModelTypeEnum | null; // Use the enum from your API types
  modelName: string | null;
  modelHyperparametersSchema: HyperparameterDefinition[]; // Schema for the selected model's HPs

  // Step 3: Hyperparameter Configuration
  configuredHyperparameters: Record<string, any>;

  // Step 4: Feature & Target Configuration (Refinement)
  selectedFeatures: string[];
  targetColumn: string | null; // Final target column selection for training

  // Step 5: Job Naming & Review
  trainingJobName: string;
  // Any other job-specific settings like description can be added here
  trainingJobDescription?: string;

  randomSeed?: number | null; // Optional random seed for reproducibility
  evalTestSplitSize?: number | null; // Optional test split size for evaluation
}

/**
 * Initial state for the TrainingJobFormData.
 */
export const initialTrainingJobFormData: TrainingJobFormData = {
  repositoryId: null,
  repositoryName: undefined,
  datasetId: null,
  datasetName: undefined,
  datasetFeatureSpace: [],
  datasetTargetColumn: null,

  modelId: null,
  modelType: null,
  modelName: null,
  modelHyperparametersSchema: [],

  configuredHyperparameters: {},

  selectedFeatures: [],
  targetColumn: null, // Default to null, will be populated from dataset or selected

  trainingJobName: "",
  trainingJobDescription: "",
};

// Types for the "Create Dataset" modal/sub-flow within the wizard
export interface NewDatasetWizardData {
  name: string;
  description?: string;
  feature_columns: string[];
  target_column: string;
  cleaning_rules: CleaningRuleConfig[]; // Re-use from api/dataset.ts
}