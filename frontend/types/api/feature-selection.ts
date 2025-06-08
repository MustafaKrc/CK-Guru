// frontend/types/api/feature-selection.ts

export interface FeatureSelectionParamDefinition {
  name: string;
  type: 'integer' | 'float' | 'string' | 'boolean' | 'enum';
  description: string;
  default?: any;
  options?: any[];
}

export interface FeatureSelectionDefinition {
  name: string;
  display_name: string;
  description: string;
  parameters: FeatureSelectionParamDefinition[];
  is_implemented: boolean;
}