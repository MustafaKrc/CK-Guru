# shared/feature_selection.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field


class FeatureSelectionParamDefinition(BaseModel):
    """
    Defines the structure for a feature selection algorithm's parameter,
    used for populating UI and validation.
    """

    name: str = Field(..., description="Parameter name used in the config.")
    type: str = Field(
        ..., description="Data type (e.g., 'integer', 'float', 'string', 'enum')."
    )
    description: str = Field(
        ..., description="User-friendly description of the parameter."
    )
    default: Optional[Any] = Field(None, description="Default value if not provided.")
    options: Optional[List[Any]] = Field(
        None, description="List of valid choices for 'enum' type."
    )
    range: Optional[Dict[str, Optional[float]]] = Field(
        None, description="e.g., {'min': 0.1, 'max': 1.0, 'step': 0.01}"
    )


class FeatureSelectionDefinition(BaseModel):
    """
    Schema representing the definition of a feature selection algorithm,
    used for syncing with the database and exposing via API.
    """

    name: str = Field(
        ..., description="Unique identifier name of the algorithm (e.g., 'cbfs')."
    )
    display_name: str = Field(
        ...,
        description="User-friendly name for the UI (e.g., 'Correlation-Based Feature Selection').",
    )
    description: str = Field(..., description="Explanation of what the algorithm does.")
    parameters: List[FeatureSelectionParamDefinition] = Field(default_factory=list)
    is_implemented: bool = True


class FeatureSelectionStrategy(ABC):
    """
    Abstract Base Class for a feature selection algorithm (Strategy Pattern).
    All concrete feature selection algorithms must inherit from this class.
    """

    # --- Metadata to be overridden by subclasses ---
    algorithm_name: str = "base_algorithm"
    display_name: str = "Base Algorithm"
    description: str = "Base description for a feature selection algorithm."
    parameters: List[FeatureSelectionParamDefinition] = []
    # --- End Metadata ---

    def get_definition(self) -> FeatureSelectionDefinition:
        """Returns the Pydantic model definition of the algorithm."""
        return FeatureSelectionDefinition(
            name=self.algorithm_name,
            display_name=self.display_name,
            description=self.description,
            parameters=self.parameters,
            is_implemented=True,
        )

    @abstractmethod
    def select_features(
        self, dataframe: pd.DataFrame, target_column: str, params: Dict[str, Any]
    ) -> List[str]:
        """
        Executes the feature selection logic on the provided DataFrame.

        Args:
            dataframe (pd.DataFrame): The input dataframe containing only feature columns.
            target_column (pd.Series): The series containing the target variable.
            params (Dict[str, Any]): Parameters for this specific execution, from the dataset config.

        Returns:
            List[str]: A list of the names of the selected features.
        """
        pass
