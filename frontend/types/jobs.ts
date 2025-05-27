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
  default_value?: any; 
  example_value?: any; 
  options?: Array<{ value: string | number | boolean; label: string }>; // Value can be boolean for boolean type with choices
  range?: { min?: number; max?: number; step?: number };
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
  datasetName?: string; 
  datasetFeatureSpace: string[]; 
  datasetTargetColumn?: string | null; // The target column defined in the dataset's config

  // Step 2: Model Type Selection
  modelType: ModelTypeEnum | null; 
  modelDisplayName?: string; 
  modelHyperparametersSchema: HyperparameterDefinition[];

  // Step 3: Hyperparameter Configuration
  configuredHyperparameters: Record<string, any>;

  // Step 4: Feature & Target Configuration (Training Specific)
  selectedFeatures: string[];
  trainingTargetColumn: string | null; // The target column to be used for this specific training run

  // Step 5: Job Naming & Review
  trainingJobName: string; // Name for the TrainingJobDB record
  modelBaseName: string;   // Base name for the MLModelDB record (backend will add version)
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

  modelType: null,
  modelDisplayName: undefined,
  modelHyperparametersSchema: [],

  configuredHyperparameters: {},

  selectedFeatures: [],
  trainingTargetColumn: null,

  trainingJobName: "",
  modelBaseName: "",
  trainingJobDescription: "",
};


// Types for the "Create Dataset" modal/sub-flow within the wizard
export interface NewDatasetWizardData {
  name: string;
  description?: string;
  feature_columns: string[];
  target_column: string;
  cleaning_rules: CleaningRuleConfig[];
}