// frontend/components/jobs/hp-search/SelectModelForHpSearchStep.tsx
"use client";

import React, { useState, useEffect } from "react";
import { HpSearchJobFormData } from "@/types/jobs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Brain } from "lucide-react";
import { apiService, handleApiError } from "@/lib/apiService";
import { AvailableModelType } from "@/types/api/ml-model";
import { ModelTypeEnum } from "@/types/api/enums";
import { useToast } from "@/hooks/use-toast";

interface SelectModelForHpSearchStepProps {
  formData: HpSearchJobFormData;
  updateFormData: (updates: Partial<HpSearchJobFormData>) => void;
}

export const SelectModelForHpSearchStep: React.FC<SelectModelForHpSearchStepProps> = ({
  formData,
  updateFormData,
}) => {
  const { toast } = useToast();
  const [availableModelTypes, setAvailableModelTypes] = useState<AvailableModelType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTypes = async () => {
      setIsLoading(true);
      try {
        const types = await apiService.getAvailableModelTypes();
        setAvailableModelTypes(types || []);
      } catch (err) {
        handleApiError(err, "Failed to load model types");
        setError("Could not load model types.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchTypes();
  }, []);

  const handleModelTypeSelect = (selectedTypeName: string) => {
    const selectedTypeDetails = availableModelTypes.find(
      (type) => type.type_name === selectedTypeName
    );
    if (selectedTypeDetails) {
      updateFormData({
        modelType: selectedTypeDetails.type_name as ModelTypeEnum,
        modelDisplayName: selectedTypeDetails.display_name,
        modelHyperparametersSchema: selectedTypeDetails.hyperparameter_schema || [],
        hpSpace: [], // Reset search space when model changes
        modelBaseName: `${formData.datasetName || "ds"}_${selectedTypeDetails.type_name.split("_").pop() || "model"}`,
      });
      toast({
        title: "Model Selected",
        description: `Ready to configure search space for ${selectedTypeDetails.display_name}.`,
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Brain className="mr-2 h-5 w-5 text-primary" />
          Model Architecture
        </CardTitle>
        <CardDescription>
          Choose the model architecture for which to optimize hyperparameters.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Label htmlFor="model-type-select">Model Type *</Label>
        {isLoading ? (
          <Skeleton className="h-10 w-full mt-2" />
        ) : (
          <Select
            value={formData.modelType || ""}
            onValueChange={handleModelTypeSelect}
            disabled={availableModelTypes.length === 0}
          >
            <SelectTrigger id="model-type-select">
              <SelectValue placeholder="Select a model type..." />
            </SelectTrigger>
            <SelectContent>
              {availableModelTypes.map((type) => (
                <SelectItem key={type.type_name} value={type.type_name}>
                  {type.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {error && (
          <Alert variant="destructive" className="mt-2">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};
