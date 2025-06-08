// frontend/app/datasets/create/FeatureSelectionStep.tsx
import React from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { HelpCircle, WandSparkles, Settings2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';

import { FeatureSelectionConfig, FeatureSelectionDefinition } from '@/types/api';

interface FeatureSelectionStepProps {
  availableAlgorithms: FeatureSelectionDefinition[];
  selectionConfig: FeatureSelectionConfig | null;
  onConfigChange: (config: FeatureSelectionConfig | null) => void;
}

const ParamInput: React.FC<{
  paramDef: FeatureSelectionDefinition['parameters'][0];
  value: any;
  onChange: (value: any) => void;
}> = ({ paramDef, value, onChange }) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val: string | number | boolean = e.target.value;
    if (paramDef.type === "integer") val = parseInt(e.target.value, 10) || 0;
    else if (paramDef.type === "float") val = parseFloat(e.target.value) || 0.0;
    onChange(val);
  };

  switch (paramDef.type) {
    case 'integer':
    case 'float':
      return <Input type="number" value={String(value ?? '')} onChange={handleChange} step={paramDef.type === 'float' ? 'any' : 1} className="h-9" />;
    case 'boolean':
      return <Switch checked={!!value} onCheckedChange={onChange} />;
    case 'enum':
      return (
        <Select value={String(value ?? '')} onValueChange={onChange}>
          <SelectTrigger className="h-9"><SelectValue placeholder={`Select ${paramDef.name}...`} /></SelectTrigger>
          <SelectContent>{paramDef.options?.map(opt => <SelectItem key={String(opt)} value={String(opt)}>{String(opt)}</SelectItem>)}</SelectContent>
        </Select>
      );
    default:
      return <Input type="text" value={String(value ?? '')} onChange={handleChange} className="h-9" />;
  }
};

export const FeatureSelectionStep: React.FC<FeatureSelectionStepProps> = ({
  availableAlgorithms,
  selectionConfig,
  onConfigChange
}) => {
  const isEnabled = !!selectionConfig;
  const selectedAlgorithm = isEnabled ? availableAlgorithms.find(a => a.name === selectionConfig.name) : null;

  const handleToggle = (checked: boolean) => {
    if (checked) {
      // Enable with the first available algorithm by default
      if (availableAlgorithms.length > 0) {
        const firstAlgo = availableAlgorithms[0];
        const defaultParams = firstAlgo.parameters.reduce((acc, param) => {
            if (param.default !== undefined) {
                acc[param.name] = param.default;
            }
            return acc;
        }, {} as Record<string, any>);
        onConfigChange({ name: firstAlgo.name, params: defaultParams });
      }
    } else {
      onConfigChange(null);
    }
  };

  const handleAlgorithmChange = (algoName: string) => {
    const newAlgo = availableAlgorithms.find(a => a.name === algoName);
    if (newAlgo) {
        const defaultParams = newAlgo.parameters.reduce((acc, param) => {
            if (param.default !== undefined) {
                acc[param.name] = param.default;
            }
            return acc;
        }, {} as Record<string, any>);
      onConfigChange({ name: newAlgo.name, params: defaultParams });
    }
  };
  
  const handleParamChange = (paramName: string, value: any) => {
    if (selectionConfig) {
      onConfigChange({
        ...selectionConfig,
        params: {
          ...selectionConfig.params,
          [paramName]: value,
        },
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
            <div>
                <CardTitle className="flex items-center"><WandSparkles className="mr-2 h-5 w-5 text-primary"/>Feature Selection</CardTitle>
                <CardDescription>Optionally apply a feature selection algorithm after cleaning the data.</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
                <Label htmlFor="enable-fs" className="text-sm">Enable</Label>
                <Switch id="enable-fs" checked={isEnabled} onCheckedChange={handleToggle} />
            </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {!isEnabled ? (
          <Alert variant="default">
            <AlertDescription>Feature selection is disabled. All configured features will be included in the final dataset.</AlertDescription>
          </Alert>
        ) : availableAlgorithms.length === 0 ? (
          <Alert variant="default">
            <AlertDescription>No feature selection algorithms are available from the backend worker.</AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="algorithm-select">Algorithm</Label>
                <Select value={selectionConfig?.name || ""} onValueChange={handleAlgorithmChange}>
                    <SelectTrigger id="algorithm-select"><SelectValue placeholder="Select an algorithm..." /></SelectTrigger>
                    <SelectContent>
                        {availableAlgorithms.map(algo => <SelectItem key={algo.name} value={algo.name}>{algo.display_name}</SelectItem>)}
                    </SelectContent>
                </Select>
                {selectedAlgorithm && <p className="text-xs text-muted-foreground">{selectedAlgorithm.description}</p>}
            </div>

            {selectedAlgorithm && selectedAlgorithm.parameters.length > 0 && (
              <Card className="bg-muted/30">
                <CardHeader className="pb-3 pt-4">
                    <CardTitle className="text-base flex items-center"><Settings2 className="mr-2 h-4 w-4 text-primary"/>Parameters</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {selectedAlgorithm.parameters.map(paramDef => (
                     <div key={paramDef.name} className="flex items-center justify-between">
                        <div className="flex items-center space-x-1.5">
                            <Label htmlFor={`param-${paramDef.name}`} className="text-sm">{paramDef.name}</Label>
                            <TooltipProvider delayDuration={100}>
                                <Tooltip>
                                    <TooltipTrigger asChild><HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help"/></TooltipTrigger>
                                    <TooltipContent className="max-w-xs text-xs"><p>{paramDef.description}</p></TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                        <div className="w-1/2">
                            <ParamInput 
                                paramDef={paramDef}
                                value={selectionConfig?.params[paramDef.name] ?? paramDef.default}
                                onChange={(value) => handleParamChange(paramDef.name, value)}
                            />
                        </div>
                     </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};