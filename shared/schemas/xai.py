# shared/schemas/xai.py
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

# --- Schemas for XAI result_data structures ---

class FilePredictionDetail(BaseModel):
    """Detailed prediction result for a single file/class instance."""
    file: Optional[str] = Field(None, description="File path.")
    class_name: Optional[str] = Field(None, alias="class", description="Class name (if applicable).") # Use alias if frontend expects 'class'
    prediction: int = Field(..., description="Predicted label (e.g., 0 or 1) for this instance.")
    probability: float = Field(..., description="Probability of the positive class (defect-prone) for this instance.")

    model_config = ConfigDict(populate_by_name=True) # Allow using alias 'class'

class FeatureImportanceValue(BaseModel):
    feature: str = Field(..., description="Name of the feature.")
    importance: float = Field(..., description="Calculated importance score (e.g., mean absolute SHAP).")

class FeatureImportanceResultData(BaseModel):
    feature_importances: List[FeatureImportanceValue] = Field(..., description="List of feature importance scores.")

class FeatureSHAPValue(BaseModel):
    feature: str = Field(..., description="Name of the feature.")
    value: float = Field(..., description="The calculated SHAP value for this feature and instance.")
    feature_value: Any = Field(None, description="The actual value of the feature for this instance (optional).")

class InstanceSHAPResult(BaseModel):
    file: Optional[str] = Field(None, description="File path associated with this instance.")
    class_name: Optional[str] = Field(None, alias="class", description="Class name associated with this instance (if applicable).")
    shap_values: List[FeatureSHAPValue] = Field(..., description="List of SHAP values per feature for this instance.")
    base_value: Optional[float] = Field(None, description="SHAP base value for this instance's prediction.")

    model_config = {"populate_by_name": True}

class SHAPResultData(BaseModel):
    instance_shap_values: List[InstanceSHAPResult] = Field(..., description="List containing SHAP value details for each analyzed file/class instance.")

class InstanceLIMEResult(BaseModel):
    file: Optional[str] = Field(None, description="File path.")
    class_name: Optional[str] = Field(None, alias="class", description="Class name.")
    explanation: List[Tuple[str, float]] = Field(..., description="List of (feature, weight) tuples from LIME.")

    model_config = {"populate_by_name": True}

class LIMEResultData(BaseModel):
    instance_lime_values: List[InstanceLIMEResult] = Field(..., description="List of LIME explanations per instance.")

class CounterfactualExample(BaseModel):
     features: Dict[str, Any] = Field(..., description="The counterfactual feature values.")
     outcome_probability: float = Field(..., description="Predicted probability with these counterfactual features.")

class InstanceCounterfactualResult(BaseModel):
    file: Optional[str] = Field(None, description="File path.")
    class_name: Optional[str] = Field(None, alias="class", description="Class name.")
    counterfactuals: List[CounterfactualExample] = Field(..., description="List of counterfactual examples found.")

    model_config = {"populate_by_name": True}

class CounterfactualResultData(BaseModel):
    instance_counterfactuals: List[InstanceCounterfactualResult] = Field(...)

class DecisionPathNode(BaseModel):
    id: str
    condition: Optional[str] = None # None for leaf nodes
    samples: Optional[int] = None
    # Value might represent class probabilities or counts
    value: Optional[List[float]] | Optional[List[int]] = None

class DecisionPathEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None # e.g., "True" / "False" or feature value threshold

class InstanceDecisionPath(BaseModel):
    file: Optional[str] = Field(None, description="File path.")
    class_name: Optional[str] = Field(None, alias="class", description="Class name.")
    nodes: List[DecisionPathNode]
    edges: List[DecisionPathEdge]

    model_config = {"populate_by_name": True}

class DecisionPathResultData(BaseModel):
    instance_decision_paths: List[InstanceDecisionPath] = Field(..., description="Decision path details for each applicable instance.")