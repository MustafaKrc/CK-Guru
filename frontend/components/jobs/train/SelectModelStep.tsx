// frontend/components/jobs/train/SelectModelStep.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { TrainingJobFormData } from '@/types/jobs';
import { Button }
from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Brain } from 'lucide-react'; // Icon for models
import { apiService, handleApiError } from '@/lib/apiService';
import { MLModelRead, PaginatedMLModelRead } from '@/types/api/ml-model';
import { useToast } from '@/hooks/use-toast';

interface SelectModelStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  onStepComplete: () => void; // To enable "Next" button in parent
}

export const SelectModelStep: React.FC<SelectModelStepProps> = ({
  formData,
  updateFormData,
  onStepComplete,
}) => {
  const { toast } = useToast();
  const [availableModels, setAvailableModels] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch models when repositoryId changes or component mounts with a repositoryId
  const fetchModelsForRepository = useCallback(async (repoId: number) => {
    setIsLoadingModels(true);
    setError(null);
    setAvailableModels([]); // Clear previous models
    try {
      // Use the endpoint that lists models for a specific repository
      const response = await apiService.get<PaginatedMLModelRead>(`/repositories/${repoId}/models?limit=200`);
      // Filter for models that have a dataset_id, as models without it can't be used for training
      // Also, models should ideally have an artifact path if they are pre-trained bases,
      // or be of a type that can be trained from scratch.
      // For now, let's assume the backend list provides usable model *types* or *bases*.
      // A crucial filter would be if a model type is actually trainable.
      // For simplicity, we list all for now, selection implies trainability.
      setAvailableModels(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load models for repository");
      setError(err instanceof Error ? err.message : "Could not load models.");
    } finally {
      setIsLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    if (formData.repositoryId) {
      fetchModelsForRepository(formData.repositoryId);
    } else {
      setAvailableModels([]); // No repo, no models to show
    }
  }, [formData.repositoryId, fetchModelsForRepository]);

  const handleModelSelect = async (modelIdString: string) => {
    if (!modelIdString) {
        updateFormData({
            modelId: null,
            modelType: null,
            modelName: null,
            modelHyperparametersSchema: [],
            configuredHyperparameters: {}, // Reset HPs
        });
        return;
    }
    const modelId = parseInt(modelIdString);
    const selectedModelFromList = availableModels.find(m => m.id === modelId);

    if (!selectedModelFromList) return;

    setIsLoadingModels(true); // Indicate loading for model details
    try {
      // Fetch full model details to get the hyperparameter_schema
      // The backend's /ml/models/{model_id} endpoint MUST return `hyperparameter_schema`
      const modelDetails = await apiService.getModelDetails(modelId);

      if (!modelDetails.hyperparameter_schema) {
        console.warn(`Model ${modelDetails.name} (ID: ${modelId}) is missing hyperparameter_schema.`);
        toast({
            title: "Model Configuration Incomplete",
            description: `The selected model '${modelDetails.name}' does not have a defined hyperparameter schema. Defaulting to an empty schema. You might need to define hyperparameters manually or check model setup.`,
            variant: "default", // "default" because it's a warning, not a hard error for user
            duration: 7000,
        });
      }
      
      // Pre-fill configuredHyperparameters with default_values from the schema
      const initialConfiguredHPs: Record<string, any> = {};
      (modelDetails.hyperparameter_schema || []).forEach(param => {
        if (param.default_value !== undefined) {
          initialConfiguredHPs[param.name] = param.default_value;
        } else if (param.example_value !== undefined) {
             // Fallback to example_value if default_value is not present
            initialConfiguredHPs[param.name] = param.example_value;
        }
      });


      updateFormData({
        modelId: modelDetails.id,
        modelType: modelDetails.model_type,
        modelName: modelDetails.name, // This is the base model name
        modelHyperparametersSchema: modelDetails.hyperparameter_schema || [],
        configuredHyperparameters: initialConfiguredHPs,
      });
      toast({ title: "Model Selected", description: `${modelDetails.name} (v${modelDetails.version}) ready for configuration.`});
      // onStepComplete(); // Parent handles enabling Next button based on formData
    } catch (err) {
      handleApiError(err, "Failed to load model details");
      updateFormData({ // Reset if fetching details fails
        modelId: null,
        modelType: null,
        modelName: null,
        modelHyperparametersSchema: [],
        configuredHyperparameters: {},
      });
    } finally {
        setIsLoadingModels(false);
    }
  };

  if (!formData.repositoryId) {
    return (
      <Alert variant="default">
        <AlertDescription>
          Please select a repository in the previous step to see available models.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Brain className="mr-2 h-5 w-5 text-primary"/>Model Selection</CardTitle>
          <CardDescription>
            Choose a base model architecture to train. Hyperparameters can be configured in the next step.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="model-select">Available Models *</Label>
            {isLoadingModels && availableModels.length === 0 ? <Skeleton className="h-10 w-full" /> : (
              <Select
                value={formData.modelId?.toString() || ""}
                onValueChange={handleModelSelect}
                disabled={availableModels.length === 0 || isLoadingModels}
              >
                <SelectTrigger id="model-select" disabled={isLoadingModels || availableModels.length === 0}>
                  <SelectValue placeholder={
                      isLoadingModels ? "Loading models..." :
                      availableModels.length === 0 ? "No models available for this repository" :
                      "Select a model..."
                  } />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.map((model) => (
                    <SelectItem key={model.id} value={model.id.toString()}>
                      {model.name} (v{model.version}) - {model.model_type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {error && <Alert variant="destructive" className="mt-2"><AlertDescription>{error}</AlertDescription></Alert>}
            {availableModels.length === 0 && !isLoadingModels && !error && formData.repositoryId && (
                 <Alert variant="default" className="mt-2">
                    <AlertDescription>
                        No models found for the selected repository. Models typically appear after training or if base model types are registered.
                    </AlertDescription>
                </Alert>
            )}
          </div>

          {formData.modelId && formData.modelName && (
            <Alert variant="default" className="mt-4 bg-primary/5 border-primary/20">
              <div className="ml-2">
                <p className="font-semibold text-primary">Selected Model: {formData.modelName}</p>
                <p className="text-xs text-muted-foreground">Type: {formData.modelType}</p>
                {formData.modelHyperparametersSchema.length > 0 ? (
                     <p className="text-xs text-muted-foreground">
                        Configurable Hyperparameters: {formData.modelHyperparametersSchema.length}
                    </p>
                ) : (
                    <p className="text-xs text-orange-600 dark:text-orange-400">
                        Note: No configurable hyperparameters schema found for this model. Default values will be used or manual input may be required.
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