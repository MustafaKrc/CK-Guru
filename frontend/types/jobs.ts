// frontend/types/jobs.ts

import { ModelTypeEnum, ObjectiveMetricEnum, SamplerTypeEnum, PrunerTypeEnum } from "./api/enums";
import { CleaningRuleConfig } from "./api/dataset";
import { HPSuggestion, OptunaConfig } from "./api/hp-search-job";

export interface HyperparameterDefinition {
  name: string;
  type: "integer" | "float" | "string" | "boolean" | "enum" | "text_choice";
  description?: string;
  default_value?: any;
  example_value?: any;
  options?: Array<{ value: string | number | boolean; label: string }>;
  range?: { min?: number; max?: number; step?: number };
  required?: boolean;
}

export interface TrainingJobFormData {
  // Step 1: Repository & Dataset
  repositoryId: number | null;
  repositoryName?: string;
  datasetId: number | null;
  datasetName?: string; 
  datasetFeatureSpace: string[]; 
  datasetTargetColumn?: string | null;

  // Step 2: Model Type Selection
  modelType: ModelTypeEnum | null; 
  modelDisplayName?: string; 
  modelHyperparametersSchema: HyperparameterDefinition[];

  // Step 3: Hyperparameter Configuration
  configuredHyperparameters: Record<string, any>;

  // Step 4: Feature & Target Configuration (Training Specific)
  selectedFeatures: string[];
  trainingTargetColumn: string | null;

  trainingJobName: string;
  modelBaseName: string;
  trainingJobDescription?: string;

  randomSeed?: number | null;
  evalTestSplitSize?: number | null;
}

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


export interface HpSearchJobFormData {
  // Step 1
  repositoryId: number | null;
  repositoryName?: string;
  datasetId: number | null;
  datasetName?: string;
  datasetFeatureSpace: string[];
  datasetTargetColumn: string | null;

  // Step 2
  modelType: ModelTypeEnum | null;
  modelDisplayName?: string;
  modelHyperparametersSchema: HyperparameterDefinition[];

  // Step 3
  hpSpace: HPSuggestion[];

  // Step 4
  optunaConfig: OptunaConfig;

  // Step 5
  studyName: string;
  saveBestModel: boolean;
  modelBaseName: string;
}

// Initial state for the HP Search form
export const initialHpSearchJobFormData: HpSearchJobFormData = {
  repositoryId: null,
  repositoryName: undefined,
  datasetId: null,
  datasetName: undefined,
  datasetFeatureSpace: [],
  datasetTargetColumn: null,

  modelType: null,
  modelDisplayName: undefined,
  modelHyperparametersSchema: [],
  
  hpSpace: [],
  
  optunaConfig: {
    n_trials: 20,
    objective_metric: ObjectiveMetricEnum.F1_WEIGHTED,
    sampler_type: SamplerTypeEnum.TPE,
    pruner_type: PrunerTypeEnum.MEDIAN,
    continue_if_exists: false,
    hp_search_cv_folds: 3,
    sampler_config: {},
    pruner_config: {},
  },
  
  studyName: "",
  saveBestModel: true,
  modelBaseName: "",
};