// frontend/app/datasets/create/constants.ts

export interface MetricDefinition {
  id: string;
  name: string;
  description: string;
  group: "CK" | "CommitGuru" | "Delta CK";
}

// Raw column names from backend (shared/db/__init__.py)
// These should be kept in sync with the backend.
const RAW_CK_METRIC_COLUMNS = [
  "cbo",
  "cboModified",
  "fanin",
  "fanout",
  "wmc",
  "dit",
  "noc",
  "rfc",
  "lcom",
  "lcom_norm",
  "tcc",
  "lcc",
  "totalMethodsQty",
  "staticMethodsQty",
  "publicMethodsQty",
  "privateMethodsQty",
  "protectedMethodsQty",
  "defaultMethodsQty",
  "visibleMethodsQty",
  "abstractMethodsQty",
  "finalMethodsQty",
  "synchronizedMethodsQty",
  "totalFieldsQty",
  "staticFieldsQty",
  "publicFieldsQty",
  "privateFieldsQty",
  "protectedFieldsQty",
  "defaultFieldsQty",
  "finalFieldsQty",
  "synchronizedFieldsQty",
  "nosi",
  "loc",
  "returnQty",
  "loopQty",
  "comparisonsQty",
  "tryCatchQty",
  "parenthesizedExpsQty",
  "stringLiteralsQty",
  "numbersQty",
  "assignmentsQty",
  "mathOperationsQty",
  "variablesQty",
  "maxNestedBlocksQty",
  "anonymousClassesQty",
  "innerClassesQty",
  "lambdasQty",
  "uniqueWordsQty",
  "modifiers",
  "logStatementsQty",
];

const RAW_COMMIT_GURU_METRIC_COLUMNS = [
  "ns",
  "nd",
  "nf",
  "entropy",
  "la",
  "ld",
  "lt",
  "ndev",
  "age",
  "nuc",
  "exp",
  "rexp",
  "sexp",
];

// Helper to format display names
const formatDisplayName = (id: string): string => {
  if (id.startsWith("d_")) {
    id = id.substring(2); // Remove "d_"
  }
  // Add spaces before capital letters (e.g., totalMethodsQty -> Total Methods Qty)
  // Capitalize first letter
  return id
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .replace(/_/g, " "); // Replace underscores with spaces
};

// TODO: These definitions should be fetched from the backend to ensure consistency and allow for dynamic updates.
const METRIC_DEFINITIONS: Record<string, string> = {
  // Chidamber & Kemerer Metrics
  cbo: "Coupling Between Objects: Counts how many other classes are coupled to a given class (efferent couplings).",
  cboModified:
    "CBO Modified: CBO, but only counting classes from the project (not from external libraries).",
  fanin: "Fan-in: Number of other classes that reference a given class (afferent couplings).",
  fanout: "Fan-out: Number of other classes referenced by a given class (efferent couplings).",
  wmc: "Weighted Methods per Class: Sum of the cyclomatic complexities of all methods in a class.",
  dit: "Depth of Inheritance Tree: The maximum length from the class to the root of the inheritance tree.",
  noc: "Number of Children: The number of immediate subclasses of a class.",
  rfc: "Response for a Class: The number of methods that can be invoked in response to a message to an object of the class.",
  lcom: "Lack of Cohesion in Methods: Measures the dissimilarity of methods in a class via instance variables.",
  lcom_norm: "Lack of Cohesion in Methods (Normalized): LCOM normalized to be between 0 and 1.",
  tcc: "Tight Class Cohesion: Measures the percentage of pairs of public methods of a class that are cohesive.",
  lcc: "Loose Class Cohesion: Measures the cohesion of a class as the relative number of pairs of methods that access in common at least one attribute of the class.",
  totalMethodsQty: "Total Methods Quantity: The total number of methods in a class.",
  staticMethodsQty: "Static Methods Quantity: The number of static methods in a class.",
  publicMethodsQty: "Public Methods Quantity: The number of public methods.",
  privateMethodsQty: "Private Methods Quantity: The number of private methods.",
  protectedMethodsQty: "Protected Methods Quantity: The number of protected methods.",
  defaultMethodsQty: "Default Methods Quantity: The number of default (package-private) methods.",
  visibleMethodsQty: "Visible Methods Quantity: The number of methods not private.",
  abstractMethodsQty: "Abstract Methods Quantity: The number of abstract methods.",
  finalMethodsQty: "Final Methods Quantity: The number of final methods.",
  synchronizedMethodsQty: "Synchronized Methods Quantity: The number of synchronized methods.",
  totalFieldsQty: "Total Fields Quantity: The total number of fields in a class.",
  staticFieldsQty: "Static Fields Quantity: The number of static fields.",
  publicFieldsQty: "Public Fields Quantity: The number of public fields.",
  privateFieldsQty: "Private Fields Quantity: The number of private fields.",
  protectedFieldsQty: "Protected Fields Quantity: The number of protected fields.",
  defaultFieldsQty: "Default Fields Quantity: The number of default (package-private) fields.",
  finalFieldsQty: "Final Fields Quantity: The number of final fields.",
  synchronizedFieldsQty: "Synchronized Fields Quantity: The number of synchronized fields.",
  nosi: "Number of Static Invocations: The number of invocations to static methods.",
  loc: "Lines of Code: The number of lines of code in the class (excluding comments and blank lines).",
  returnQty: "Return Quantity: The number of return statements in a method.",
  loopQty: "Loop Quantity: The number of loops (for, while, do-while) in a method.",
  comparisonsQty:
    "Comparisons Quantity: The number of comparison operators (e.g., >, <, ==) in a method.",
  tryCatchQty: "Try-Catch Quantity: The number of try-catch blocks in a method.",
  parenthesizedExpsQty:
    "Parenthesized Expressions Quantity: The number of parenthesized expressions.",
  stringLiteralsQty: "String Literals Quantity: The number of string literals.",
  numbersQty: "Numbers Quantity: The number of numeric literals.",
  assignmentsQty: "Assignments Quantity: The number of assignment operations (=, +=, etc.).",
  mathOperationsQty: "Math Operations Quantity: The number of math operations (+, -, *, etc.).",
  variablesQty: "Variables Quantity: The number of declared local variables.",
  maxNestedBlocksQty:
    "Max Nested Blocks Quantity: The maximum nesting level of blocks (e.g., if, for, while).",
  anonymousClassesQty: "Anonymous Classes Quantity: The number of anonymous classes declared.",
  innerClassesQty: "Inner Classes Quantity: The number of inner classes declared.",
  lambdasQty: "Lambdas Quantity: The number of lambda expressions.",
  uniqueWordsQty:
    "Unique Words Quantity: The number of unique words in the source code of the class.",
  modifiers:
    "Modifiers: A bitmask representing class/method/field modifiers (e.g., public, static, final).",
  logStatementsQty: "Log Statements Quantity: The number of logging statements.",

  // CommitGuru Metrics (Process Metrics)
  ns: "Number of modified Subsystems: Number of distinct top-level directories of files modified in a commit.",
  nd: "Number of modified Directories: Number of distinct directories modified in a commit.",
  nf: "Number of modified Files: Number of files modified in a commit.",
  entropy:
    "Entropy of modified files: Distribution of changes across files. Higher entropy means changes are more spread out.",
  la: "Lines Added: Total number of lines of code added in a commit.",
  ld: "Lines Deleted: Total number of lines of code deleted in a commit.",
  lt: "Lines of code in a file (pre-change): Sum of the sizes of all modified files before the commit.",
  ndev: "Number of Developers: Number of unique developers who have previously modified the files in the commit.",
  age: "Age of a file (weeks): The average time interval between the last change and the current change for all files in the commit.",
  nuc: "Number of Unique Changes: Number of unique commits that have previously modified the files in the commit.",
  exp: "Developer Experience: The total number of commits made by the author of the commit.",
  rexp: "Recent Developer Experience: Developer experience, weighted by the age of each commit (more recent commits count more).",
  sexp: "Subsystem Developer Experience: Number of commits made by the author in the same subsystem as the modified files.",
};

export const STATIC_AVAILABLE_METRICS: MetricDefinition[] = [
  ...RAW_CK_METRIC_COLUMNS.map((col) => ({
    id: col,
    name: formatDisplayName(col),
    description: METRIC_DEFINITIONS[col] || `Chidamber & Kemerer metric: ${formatDisplayName(col)}`,
    group: "CK" as const,
  })),
  ...RAW_COMMIT_GURU_METRIC_COLUMNS.map((col) => ({
    id: col,
    name: formatDisplayName(col),
    description: METRIC_DEFINITIONS[col] || `CommitGuru metric: ${formatDisplayName(col)}`,
    group: "CommitGuru" as const,
  })),
  ...RAW_CK_METRIC_COLUMNS.map((col) => ({
    id: `d_${col}`,
    name: `Delta ${formatDisplayName(col)}`,
    description: `Change in '${formatDisplayName(col)}': Represents the difference in the metric value before and after the commit.`,
    group: "Delta CK" as const,
  })),
];

export const STATIC_AVAILABLE_TARGETS = [
  {
    id: "is_buggy",
    name: "Is Buggy (Commit-level)",
    description: "Predict if a commit introduced a bug (0 or 1).",
  },
  // { id: "is_file_buggy", name: "Is File Buggy (File-level)", description: "Predict if a file within a commit is buggy (0 or 1)." },
];

// Export raw columns if needed elsewhere, though typically only for this constant generation
export { RAW_CK_METRIC_COLUMNS, RAW_COMMIT_GURU_METRIC_COLUMNS };
