// frontend/types/api/rule.ts (or in dataset.ts)
export interface RuleParamDefinition {
  name: string;
  type: string; // e.g., 'integer', 'float', 'boolean', 'string', 'select'
  description: string;
  default?: any;
  required?: boolean; // From backend schema
  options?: string[]; // For 'select' type
}

export interface RuleDefinition {
  name: string;
  description: string;
  parameters: RuleParamDefinition[];
  is_batch_safe: boolean;
  is_implemented: boolean;
}
