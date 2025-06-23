// frontend/components/jobs/train/SelectModelStep.tsx
import React, { useState, useEffect, useCallback } from "react";
import { TrainingJobFormData } from "@/types/jobs";
import {SearchableSelect} from "@/components/ui/searchable-select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Brain } from "lucide-react";
import { apiService, handleApiError } from "@/lib/apiService";
import { AvailableModelType } from "@/types/api/ml-model";
import { ModelTypeEnum } from "@/types/api/enums";
import { useToast } from "@/hooks/use-toast";

interface SelectModelStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  onStepComplete: () => void; // Not directly used here, parent "Next" handles it
}

export const SelectModelStep: React.FC<SelectModelStepProps> = ({ formData, updateFormData }) => {
  const { toast } = useToast();
  const [availableModelTypes, setAvailableModelTypes] = useState<AvailableModelType[]>([]);
  const [isLoadingModelTypes, setIsLoadingModelTypes] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTypes = async () => {
      setIsLoadingModelTypes(true);
      setError(null);
      try {
        const types = await apiService.getAvailableModelTypes();
        setAvailableModelTypes(types || []);

        // If a modelType is already in formData (e.g., navigating back),
        // ensure its schema and derived name are re-populated correctly.
        if (formData.modelType && types) {
          const currentTypeDetails = types.find((t) => t.type_name === formData.modelType);
          if (currentTypeDetails) {
            const initialConfiguredHPs: Record<string, any> = {};
            (currentTypeDetails.hyperparameter_schema || []).forEach((param, index) => {
              const paramKey = param.name || `hp-${index}`;
              if (param.default_value !== undefined) {
                initialConfiguredHPs[paramKey] = param.default_value;
              } else if (param.example_value !== undefined) {
                initialConfiguredHPs[paramKey] = param.example_value;
              } else if (param.type === "boolean") {
                initialConfiguredHPs[paramKey] = false;
              }
            });
            // Only update if the schema isn't already there or default HPs differ
            if (
              formData.modelHyperparametersSchema.length !==
              (currentTypeDetails.hyperparameter_schema || []).length
            ) {
              updateFormData({
                modelHyperparametersSchema: currentTypeDetails.hyperparameter_schema || [],
                configuredHyperparameters: initialConfiguredHPs,
                modelDisplayName: currentTypeDetails.display_name,
                // Don't reset modelBaseName if user already set it in Review, unless it's empty
                modelBaseName:
                  formData.modelBaseName ||
                  `${formData.datasetName || "dataset"}_${currentTypeDetails.type_name.split("_").pop() || currentTypeDetails.type_name}`,
              });
            }
          }
        }
      } catch (err) {
        handleApiError(err, "Failed to load available model types");
        setError(err instanceof Error ? err.message : "Could not load model types.");
      } finally {
        setIsLoadingModelTypes(false);
      }
    };
    fetchTypes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Fetch types only on mount or if explicitly triggered

  const handleModelTypeSelect = (selectedTypeName: string) => {
    if (!selectedTypeName) {
      updateFormData({
        modelType: null,
        modelDisplayName: undefined,
        modelHyperparametersSchema: [],
        configuredHyperparameters: {},
        modelBaseName: "", // Clear suggested model base name
      });
      return;
    }

    const selectedTypeDetails = availableModelTypes.find(
      (type) => type.type_name === selectedTypeName
    );

    if (selectedTypeDetails) {
      const initialConfiguredHPs: Record<string, any> = {};
      (selectedTypeDetails.hyperparameter_schema || []).forEach((param, index) => {
        const paramKey = param.name || `hp-${index}`;
        if (param.default_value !== undefined) {
          initialConfiguredHPs[paramKey] = param.default_value;
        } else if (param.example_value !== undefined) {
          initialConfiguredHPs[paramKey] = param.example_value;
        } else if (param.type === "boolean") {
          initialConfiguredHPs[paramKey] = false;
        }
      });

      const datasetNamePrefix = formData.datasetName
        ? formData.datasetName.replace(/[^a-zA-Z0-9_]/g, "_").slice(0, 20)
        : "dataset";
      const modelTypeSuffix =
        selectedTypeDetails.type_name.split("_").pop() || selectedTypeDetails.type_name;
      const suggestedModelBaseName = `${datasetNamePrefix}_${modelTypeSuffix}`;

      updateFormData({
        modelType: selectedTypeDetails.type_name as ModelTypeEnum,
        modelDisplayName: selectedTypeDetails.display_name,
        modelHyperparametersSchema: selectedTypeDetails.hyperparameter_schema || [],
        configuredHyperparameters: initialConfiguredHPs,
        modelBaseName: suggestedModelBaseName,
      });
      toast({
        title: "Model Type Selected",
        description: `${selectedTypeDetails.display_name} hyperparameters are ready for configuration.`,
      });
    }
  };

  if (!formData.datasetId) {
    // A dataset must be selected before choosing a model type for it
    return (
      <Alert variant="default">
        <AlertDescription>
          Please select a dataset in the previous step before choosing a model type.
        </AlertDescription>
      </Alert>
    );
  }

  const modelTypeOptions = availableModelTypes.map((type) => ({
    value: type.type_name,
    label: type.display_name,
  }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Brain className="mr-2 h-5 w-5 text-primary" />
            Model Architecture
          </CardTitle>
          <CardDescription>
            Choose the type of model architecture you want to train for dataset '
            <strong>{formData.datasetName || `ID ${formData.datasetId}`}</strong>'.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="model-type-select">Model Type *</Label>
            {isLoadingModelTypes ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <SearchableSelect
                options={modelTypeOptions}
                value={formData.modelType || ""}
                onValueChange={handleModelTypeSelect}
                placeholder={
                  isLoadingModelTypes
                    ? "Loading model types..."
                    : availableModelTypes.length === 0
                      ? "No model types available"
                      : "Select a model type..."
                }
                searchPlaceholder="Search model types..."
                emptyMessage="No model type found."
                disabled={isLoadingModelTypes || availableModelTypes.length === 0}
                isLoading={isLoadingModelTypes}
              />
            )}
            {error && (
              <Alert variant="destructive" className="mt-2">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {availableModelTypes.length === 0 && !isLoadingModelTypes && !error && (
              <Alert variant="default" className="mt-2">
                <AlertDescription>
                  No model types could be loaded from the backend. Please ensure the ML worker is
                  running and configured correctly.
                </AlertDescription>
              </Alert>
            )}
          </div>

          {formData.modelType && formData.modelDisplayName && (
            <Alert variant="default" className="mt-4 bg-primary/5 border-primary/20">
              <div className="ml-2">
                <p className="font-semibold text-primary">
                  Selected Model Type: {formData.modelDisplayName}
                </p>
                <p className="text-xs text-muted-foreground">Internal Type: {formData.modelType}</p>
                <p className="text-xs text-muted-foreground">
                  Base Name for new model: <strong>{formData.modelBaseName}</strong> (you can change
                  this in Review step)
                </p>
                {formData.modelHyperparametersSchema.length > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Configurable Hyperparameters: {formData.modelHyperparametersSchema.length}
                  </p>
                ) : (
                  <p className="text-xs text-orange-600 dark:text-orange-400">
                    Note: No configurable hyperparameters schema found for this model type. Default
                    values will be used.
                  </p>
                )}
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
