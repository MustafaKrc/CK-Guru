// frontend/components/jobs/train/ConfigureFeaturesTargetStep.tsx
import React, { useState, useEffect, useMemo } from 'react';
import { TrainingJobFormData } from '@/types/jobs';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { ListFilter, TargetIcon, HelpCircle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';

interface ConfigureFeaturesTargetStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  onStepComplete: () => void; // Not directly used here, parent "Next" handles it
}

export const ConfigureFeaturesTargetStep: React.FC<ConfigureFeaturesTargetStepProps> = ({
  formData,
  updateFormData,
}) => {
  const { toast } = useToast();
  const [featureSearchTerm, setFeatureSearchTerm] = useState('');

  // Initialize selectedFeatures from formData if available, or default to all dataset features.
  // Initialize targetColumn from formData if available, or default to dataset's pre-configured target.
  useEffect(() => {
    if (formData.datasetFeatureSpace.length > 0) {
      if (formData.selectedFeatures.length === 0) { // Only initialize if not already set
        updateFormData({ selectedFeatures: [...formData.datasetFeatureSpace] });
      }
      if (!formData.targetColumn && formData.datasetTargetColumn) { // Only initialize if not already set and dataset has one
        updateFormData({ targetColumn: formData.datasetTargetColumn });
      }
    }
  }, [formData.datasetFeatureSpace, formData.datasetTargetColumn, formData.selectedFeatures.length, formData.targetColumn, updateFormData]);


  const handleFeatureToggle = (featureName: string) => {
    const newSelectedFeatures = formData.selectedFeatures.includes(featureName)
      ? formData.selectedFeatures.filter((f) => f !== featureName)
      : [...formData.selectedFeatures, featureName];
    updateFormData({ selectedFeatures: newSelectedFeatures });
  };

  const handleSelectAllFeatures = () => {
    if (formData.selectedFeatures.length === formData.datasetFeatureSpace.length) {
      updateFormData({ selectedFeatures: [] }); // Deselect all
    } else {
      updateFormData({ selectedFeatures: [...formData.datasetFeatureSpace] }); // Select all
    }
  };

  const handleTargetColumnChange = (newTarget: string) => {
    updateFormData({ targetColumn: newTarget });
  };

  const filteredAvailableFeatures = useMemo(() => {
    if (!featureSearchTerm) return formData.datasetFeatureSpace;
    return formData.datasetFeatureSpace.filter(feature =>
      feature.toLowerCase().includes(featureSearchTerm.toLowerCase())
    );
  }, [formData.datasetFeatureSpace, featureSearchTerm]);


  if (!formData.datasetId) {
    return (
      <Alert variant="default">
        <AlertDescription>
          Please select a dataset in Step 1 to configure features and target.
        </AlertDescription>
      </Alert>
    );
  }

  if (formData.datasetFeatureSpace.length === 0) {
    return (
      <Alert variant="default">
        <AlertDescription>
          The selected dataset has no features defined in its configuration. Please check the dataset.
        </AlertDescription>
      </Alert>
    );
  }
  
  const potentialTargetColumns = formData.datasetFeatureSpace.includes(formData.datasetTargetColumn || '') 
    ? formData.datasetFeatureSpace 
    : formData.datasetTargetColumn ? [formData.datasetTargetColumn, ...formData.datasetFeatureSpace] : formData.datasetFeatureSpace;


  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><ListFilter className="mr-2 h-5 w-5 text-primary"/>Feature Selection</CardTitle>
          <CardDescription>
            Select the features from dataset '<strong>{formData.datasetName || `ID ${formData.datasetId}`}</strong>' to be used for training the model.
            Currently selected: {formData.selectedFeatures.length} of {formData.datasetFeatureSpace.length}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-2 items-center">
            <Input
              type="search"
              placeholder="Search features..."
              value={featureSearchTerm}
              onChange={(e) => setFeatureSearchTerm(e.target.value)}
              className="flex-grow h-9"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleSelectAllFeatures}
              className="w-full sm:w-auto h-9"
            >
              {formData.selectedFeatures.length === formData.datasetFeatureSpace.length ? 'Deselect All' : 'Select All'}
            </Button>
          </div>
          <ScrollArea className="h-64 rounded-md border p-3">
            {filteredAvailableFeatures.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No features match your search.</p>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-2">
                {filteredAvailableFeatures.map((feature) => (
                    <div key={feature} className="flex items-center space-x-2 py-1">
                    <Checkbox
                        id={`feature-${feature}`}
                        checked={formData.selectedFeatures.includes(feature)}
                        onCheckedChange={() => handleFeatureToggle(feature)}
                    />
                    <Label htmlFor={`feature-${feature}`} className="text-sm font-normal cursor-pointer truncate" title={feature}>
                        {feature}
                    </Label>
                    </div>
                ))}
                </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><TargetIcon className="mr-2 h-5 w-5 text-primary"/>Target Variable Selection</CardTitle>
          <CardDescription>
            Confirm or select the target variable for prediction. This is typically 'is_buggy' or a similar column from your dataset.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label htmlFor="target-column-select">Target Column *</Label>
          <Select
            value={formData.targetColumn || ""}
            onValueChange={handleTargetColumnChange}
            disabled={potentialTargetColumns.length === 0}
          >
            <SelectTrigger id="target-column-select">
              <SelectValue placeholder={
                  potentialTargetColumns.length === 0 ? "No columns available" : 
                  (formData.datasetTargetColumn ? `Default: ${formData.datasetTargetColumn}` : "Select target column...")
                } />
            </SelectTrigger>
            <SelectContent>
              {potentialTargetColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                  {col === formData.datasetTargetColumn && " (Dataset Default)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {formData.targetColumn && formData.datasetTargetColumn && formData.targetColumn !== formData.datasetTargetColumn && (
             <Alert variant="default" className="mt-2 text-xs p-2">
                <HelpCircle className="h-3.5 w-3.5"/>
                <AlertDescription>
                    You have selected a different target column (<strong>{formData.targetColumn}</strong>) than the one configured during dataset creation (<strong>{formData.datasetTargetColumn}</strong>). Ensure this is intentional.
                </AlertDescription>
            </Alert>
          )}
           {!formData.targetColumn && (
             <p className="text-xs text-muted-foreground pt-1">
                Please select the column the model should predict.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};