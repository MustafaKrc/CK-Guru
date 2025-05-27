// frontend/components/jobs/train/ConfigureHyperparametersStep.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { TrainingJobFormData, HyperparameterDefinition } from '@/types/jobs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { HelpCircle, Settings2 } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ConfigureHyperparametersStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  onStepComplete: () => void; // Not directly used here, parent "Next" handles it
}

const HyperparameterInputFactory: React.FC<{
  definition: HyperparameterDefinition;
  currentValue: any;
  onChange: (value: any) => void;
}> = ({ definition, currentValue, onChange }) => {
  const { name, type, description, options, range, default_value, example_value } = definition;
  const valueToUse = currentValue !== undefined ? currentValue : (default_value !== undefined ? default_value : example_value);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val: string | number | boolean = e.target.value;
    if (type === 'integer') val = parseInt(e.target.value, 10) || 0;
    else if (type === 'float') val = parseFloat(e.target.value) || 0.0;
    onChange(val);
  };

  const handleSwitchChange = (checked: boolean) => {
    onChange(checked);
  };

  const handleSelectChange = (selectValue: string) => {
    // Convert back to number if original options were numbers
    const originalOption = options?.find(opt => String(opt.value) === selectValue);
    onChange(originalOption ? originalOption.value : selectValue);
  };

  switch (type) {
    case 'integer':
    case 'float':
      return (
        <Input
          type="number"
          id={name}
          value={String(valueToUse ?? '')} // Ensure value is string for input
          onChange={handleInputChange}
          min={range?.min}
          max={range?.max}
          step={range?.step || (type === 'float' ? 'any' : 1)}
          className="h-9"
        />
      );
    case 'string':
      return (
        <Input
          type="text"
          id={name}
          value={String(valueToUse ?? '')}
          onChange={handleInputChange}
          className="h-9"
        />
      );
    case 'boolean':
      return (
        <div className="flex items-center pt-1.5">
          <Switch
            id={name}
            checked={Boolean(valueToUse)}
            onCheckedChange={handleSwitchChange}
          />
        </div>
      );
    case 'enum':
    case 'text_choice':
      if (!options || options.length === 0) {
        return <p className="text-xs text-red-500">Error: No options defined for enum/text_choice '{name}'.</p>;
      }
      return (
        <Select
          value={String(valueToUse ?? '')}
          onValueChange={handleSelectChange}
        >
          <SelectTrigger id={name} className="h-9">
            <SelectValue placeholder={`Select ${name}...`} />
          </SelectTrigger>
          <SelectContent>
            {options.map((opt) => (
              <SelectItem key={String(opt.value)} value={String(opt.value)}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    default:
      return (
        <Input
          type="text"
          id={name}
          value={String(valueToUse ?? '')} // Default to text if type is unknown
          onChange={handleInputChange}
          className="h-9"
          placeholder={`Unknown type: ${type}`}
        />
      );
  }
};

export const ConfigureHyperparametersStep: React.FC<ConfigureHyperparametersStepProps> = ({
  formData,
  updateFormData,
}) => {
  // Local state for HPs could be used if complex validation or debouncing is needed before updating parent
  // For now, direct update to parent formData.configuredHyperparameters via HyperparameterInputFactory's onChange

  const handleHyperparameterChange = useCallback((paramName: string, value: any) => {
    updateFormData({
      configuredHyperparameters: {
        ...formData.configuredHyperparameters,
        [paramName]: value,
      },
    });
  }, [formData.configuredHyperparameters, updateFormData]);
  
  // Initialize form data if schema exists but configured HPs are empty
  useEffect(() => {
    if (formData.modelHyperparametersSchema.length > 0 && Object.keys(formData.configuredHyperparameters).length === 0) {
      const initialConfiguredHPs: Record<string, any> = {};
      formData.modelHyperparametersSchema.forEach(param => {
        if (param.default_value !== undefined) {
          initialConfiguredHPs[param.name] = param.default_value;
        } else if (param.example_value !== undefined) {
          initialConfiguredHPs[param.name] = param.example_value;
        }
        // Booleans need explicit false if not provided
        else if (param.type === 'boolean') {
             initialConfiguredHPs[param.name] = false;
        }
      });
      if (Object.keys(initialConfiguredHPs).length > 0) {
         updateFormData({ configuredHyperparameters: initialConfiguredHPs });
      }
    }
  }, [formData.modelHyperparametersSchema, formData.configuredHyperparameters, updateFormData]);


  if (!formData.modelType) {
    return (
      <Alert variant="default">
        <AlertDescription>
          Please select a model in the previous step to configure its hyperparameters.
        </AlertDescription>
      </Alert>
    );
  }

  if (formData.modelHyperparametersSchema.length === 0) {
    return (
      <Alert variant="default">
        <AlertDescription>
          No configurable hyperparameters defined for the selected model ({formData.modelType}).
          The model will be trained with its default settings.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Settings2 className="mr-2 h-5 w-5 text-primary"/>Hyperparameter Configuration</CardTitle>
          <CardDescription>
            Adjust hyperparameters for the selected model: <strong>{formData.modelType}</strong> (Type: {formData.modelType}).
            Values set here will override model defaults.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="max-h-[calc(100vh-450px)] pr-3"> {/* Adjust max-h as needed */}
            <div className="space-y-6">
              {formData.modelHyperparametersSchema.map((hpDef, index) => (
                <div key={hpDef.name || `hp-${index}`} className="grid grid-cols-1 md:grid-cols-3 gap-x-4 gap-y-2 items-start">
                  <div className="md:col-span-1 flex items-center space-x-1 pt-1.5">
                    <Label htmlFor={hpDef.name || `hp-${index}`} className="text-sm font-medium whitespace-nowrap">
                      {hpDef.name ? hpDef.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : `Parameter ${index + 1}`}
                      {hpDef.required && <span className="text-destructive ml-1">*</span>}
                    </Label>
                    {hpDef.description && (
                      <TooltipProvider delayDuration={100}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs text-xs" side="top" align="start">
                            <p>{hpDef.description}</p>
                            {hpDef.default_value !== undefined && (
                              <p className="mt-1">Default: <code className="bg-muted/50 px-1 py-0.5 rounded-sm">{String(hpDef.default_value)}</code></p>
                            )}
                            {hpDef.example_value !== undefined && hpDef.default_value === undefined && (
                              <p className="mt-1">Example: <code className="bg-muted/50 px-1 py-0.5 rounded-sm">{String(hpDef.example_value)}</code></p>
                            )}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                  <div className="md:col-span-2">
                    <HyperparameterInputFactory
                      definition={hpDef}
                      currentValue={formData.configuredHyperparameters[hpDef.name || `hp-${index}`]}
                      onChange={(value) => handleHyperparameterChange(hpDef.name || `hp-${index}`, value)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
};