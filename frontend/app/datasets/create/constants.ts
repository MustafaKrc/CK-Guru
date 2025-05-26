// frontend/app/datasets/create/constants.ts

export interface MetricDefinition {
  id: string;
  name: string;
  description: string;
  group: 'CK' | 'CommitGuru' | 'Delta CK';
}

// Raw column names from backend (shared/db/__init__.py)
// These should be kept in sync with the backend.
const RAW_CK_METRIC_COLUMNS = [
    "cbo", "cboModified", "fanin", "fanout", "wmc", "dit", "noc", "rfc", "lcom",
    "lcom_norm", "tcc", "lcc", "totalMethodsQty", "staticMethodsQty", "publicMethodsQty",
    "privateMethodsQty", "protectedMethodsQty", "defaultMethodsQty", "visibleMethodsQty",
    "abstractMethodsQty", "finalMethodsQty", "synchronizedMethodsQty", "totalFieldsQty",
    "staticFieldsQty", "publicFieldsQty", "privateFieldsQty", "protectedFieldsQty",
    "defaultFieldsQty", "finalFieldsQty", "synchronizedFieldsQty", "nosi", "loc",
    "returnQty", "loopQty", "comparisonsQty", "tryCatchQty", "parenthesizedExpsQty",
    "stringLiteralsQty", "numbersQty", "assignmentsQty", "mathOperationsQty",
    "variablesQty", "maxNestedBlocksQty", "anonymousClassesQty", "innerClassesQty",
    "lambdasQty", "uniqueWordsQty", "modifiers", "logStatementsQty"
];

const RAW_COMMIT_GURU_METRIC_COLUMNS = [
    "ns", "nd", "nf", "entropy", "la", "ld", "lt", "ndev", "age", "nuc", "exp", "rexp", "sexp"
];

// Helper to format display names
const formatDisplayName = (id: string): string => {
  if (id.startsWith("d_")) {
    id = id.substring(2); // Remove "d_"
  }
  // Add spaces before capital letters (e.g., totalMethodsQty -> Total Methods Qty)
  // Capitalize first letter
  return id
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .replace(/_/g, ' '); // Replace underscores with spaces
};


export const STATIC_AVAILABLE_METRICS: MetricDefinition[] = [
  ...RAW_CK_METRIC_COLUMNS.map(col => ({ 
    id: col, 
    name: formatDisplayName(col), 
    description: `Chidamber & Kemerer metric: ${formatDisplayName(col)}`, 
    group: 'CK' as const 
  })),
  ...RAW_COMMIT_GURU_METRIC_COLUMNS.map(col => ({ 
    id: col, 
    name: formatDisplayName(col), 
    description: `CommitGuru metric: ${formatDisplayName(col)}`, 
    group: 'CommitGuru' as const 
  })),
  ...RAW_CK_METRIC_COLUMNS.map(col => ({ 
    id: `d_${col}`, 
    name: `Delta ${formatDisplayName(col)}`, 
    description: `Change in CK metric: ${formatDisplayName(col)}`, 
    group: 'Delta CK' as const 
  })),
];


export const STATIC_AVAILABLE_TARGETS = [
  { id: "is_buggy", name: "Is Buggy (Commit-level)", description: "Predict if a commit introduced a bug (0 or 1)." },
  // { id: "is_file_buggy", name: "Is File Buggy (File-level)", description: "Predict if a file within a commit is buggy (0 or 1)." },
];

// Export raw columns if needed elsewhere, though typically only for this constant generation
export { RAW_CK_METRIC_COLUMNS, RAW_COMMIT_GURU_METRIC_COLUMNS };