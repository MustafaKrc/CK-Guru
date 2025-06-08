// frontend/types/dataset-creation.ts
import { RuleDefinition, FeatureSelectionConfig } from "@/types/api";

// Internal frontend state for cleaning rules, including user-defined parameters
export interface InternalCleaningRuleConfig extends RuleDefinition {
  enabled: boolean;
  userParams: Record<string, any>;
}

// Represents the accumulated form data throughout the dataset creation wizard
export interface CreateDatasetFormData {
  // Step 1
  repositoryId: number | null;
  repositoryName?: string;
  datasetName: string;
  datasetDescription?: string;

  // Step 2
  selectedFeatures: string[];
  targetColumn: string;

  // Step 3
  cleaningRules: InternalCleaningRuleConfig[];

  // Step 4
  featureSelectionConfig: FeatureSelectionConfig | null;
}

// Initial state for the form data
export const initialCreateDatasetFormData: CreateDatasetFormData = {
  repositoryId: null,
  datasetName: "",
  selectedFeatures: [],
  targetColumn: "is_buggy", // A sensible default
  cleaningRules: [],
  featureSelectionConfig: null,
};