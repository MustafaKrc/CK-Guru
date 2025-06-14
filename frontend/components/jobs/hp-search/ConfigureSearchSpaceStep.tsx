// frontend/components/jobs/hp-search/ConfigureSearchSpaceStep.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { HpSearchJobFormData } from "@/types/jobs";
import { HyperparameterDefinition } from "@/types/jobs";
import { HPSuggestion } from "@/types/api/hp-search-job";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { HelpCircle, WandSparkles } from "lucide-react";
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

// --- Helper Components ---

// UI Component for selecting predefined categorical choices
const CategoricalToggleGroup: React.FC<{
  options: { label: string; value: any }[];
  selectedValues: any[];
  onChange: (newValues: any[]) => void;
}> = ({ options, selectedValues, onChange }) => {
  return (
    <ToggleGroup
      type="multiple"
      variant="outline"
      value={selectedValues.map(String)} // value requires string array
      onValueChange={(values: string[]) => {
        // Convert string values back to their original types (number, boolean)
        const newSelectedValues = values.map((vStr) => {
          const option = options.find((opt) => String(opt.value) === vStr);
          return option ? option.value : vStr;
        });
        onChange(newSelectedValues);
      }}
      className="flex-wrap justify-start"
    >
      {options.map((option) => (
        <ToggleGroupItem
          key={String(option.value)}
          value={String(option.value)}
          aria-label={`Toggle ${option.label}`}
        >
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
};

interface ParamSearchConfig {
  enabled: boolean;
  suggest_type: "int" | "float" | "categorical";
  low: string;
  high: string;
  step: string;
  log: boolean;
  choices: string;
}

const getDefaultSuggestType = (type: string): "int" | "float" | "categorical" => {
  if (type === "enum" || type === "text_choice" || type === "boolean") return "categorical";
  if (type === "float") return "float";
  return "int";
};

const ParamConfigRow: React.FC<{
  definition: HyperparameterDefinition;
  config: ParamSearchConfig;
  onConfigChange: (field: keyof ParamSearchConfig, value: any) => void;
}> = ({ definition, config, onConfigChange }) => {
  if (!config) {
    return <Skeleton className="h-24 w-full" />;
  }

  const isPredefinedCategorical =
    config.suggest_type === "categorical" && definition.options && definition.options.length > 0;
  // FIX: Explicitly check if the parameter is a boolean type.
  const isBooleanType = definition.type === "boolean";

  return (
    <div className="p-4 border rounded-lg space-y-3 bg-muted/50 transition-all duration-300 ease-in-out">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-2">
          <Checkbox
            id={`enable-${definition.name}`}
            checked={config.enabled}
            onCheckedChange={(checked) => onConfigChange("enabled", !!checked)}
          />
          <Label htmlFor={`enable-${definition.name}`} className="font-semibold text-base">
            {definition.name}
          </Label>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger type="button">
                <HelpCircle className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>{definition.description || "No description."}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      <div
        className={cn(
          "grid transition-all duration-500 ease-in-out overflow-hidden",
          config.enabled ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="min-h-0">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 pt-4 pl-6">
            <div className="space-y-1">
              <Label className="text-xs">Search Type</Label>
              <Badge
                variant="secondary"
                className="capitalize flex items-center h-9 w-full justify-center text-sm"
              >
                {config.suggest_type}
              </Badge>
            </div>

            {/* --- NEW LOGIC FOR BOOLEAN / CATEGORICAL / NUMERIC --- */}

            {isBooleanType ? (
              <div className="md:col-span-2 space-y-1">
                <Label className="text-xs">Values to Test</Label>
                <div className="flex items-center gap-2 h-9">
                  <Badge variant="outline">True</Badge>
                  <Badge variant="outline">False</Badge>
                </div>
              </div>
            ) : isPredefinedCategorical ? (
              <div className="md:col-span-2 space-y-2">
                <Label className="text-xs">Choices to Search Over</Label>
                <CategoricalToggleGroup
                  options={definition.options!.map((o) => ({ label: o.label, value: o.value }))}
                  selectedValues={config.choices
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean)}
                  onChange={(newValues) => onConfigChange("choices", newValues.join(", "))}
                />
              </div>
            ) : config.suggest_type === "categorical" ? (
              <div className="md:col-span-2 space-y-1">
                <Label htmlFor={`choices-${definition.name}`} className="text-xs">
                  Choices (comma-separated)
                </Label>
                <Input
                  id={`choices-${definition.name}`}
                  value={config.choices}
                  onChange={(e) => onConfigChange("choices", e.target.value)}
                  placeholder="e.g., auto, sqrt, log2"
                />
              </div>
            ) : (
              // Fallback to numeric inputs for int/float
              <>
                <div className="space-y-1">
                  <Label htmlFor={`low-${definition.name}`} className="text-xs">
                    Low
                  </Label>
                  <Input
                    id={`low-${definition.name}`}
                    type="number"
                    value={config.low}
                    onChange={(e) => onConfigChange("low", e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`high-${definition.name}`} className="text-xs">
                    High
                  </Label>
                  <Input
                    id={`high-${definition.name}`}
                    type="number"
                    value={config.high}
                    onChange={(e) => onConfigChange("high", e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`step-${definition.name}`} className="text-xs">
                    Step (Optional)
                  </Label>
                  <Input
                    id={`step-${definition.name}`}
                    type="number"
                    value={config.step}
                    onChange={(e) => onConfigChange("step", e.target.value)}
                  />
                </div>
                <div className="flex items-center space-x-2 pt-5">
                  <Switch
                    id={`log-${definition.name}`}
                    checked={config.log}
                    onCheckedChange={(checked) => onConfigChange("log", checked)}
                  />
                  <Label htmlFor={`log-${definition.name}`} className="text-xs">
                    Log Scale
                  </Label>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const ConfigureSearchSpaceStep: React.FC<{
  formData: HpSearchJobFormData;
  updateFormData: (updates: Partial<HpSearchJobFormData>) => void;
}> = ({ formData, updateFormData }) => {
  const [paramConfigs, setParamConfigs] = useState<Record<string, ParamSearchConfig>>({});

  useEffect(() => {
    const newConfigs: Record<string, ParamSearchConfig> = {};
    formData.modelHyperparametersSchema.forEach((param) => {
      const existingConfig = formData.hpSpace.find((s) => s.param_name === param.name);
      newConfigs[param.name] = {
        enabled: !!existingConfig,
        suggest_type: existingConfig?.suggest_type || getDefaultSuggestType(param.type),
        low: existingConfig?.low?.toString() ?? param.range?.min?.toString() ?? "",
        high: existingConfig?.high?.toString() ?? param.range?.max?.toString() ?? "",
        step: existingConfig?.step?.toString() ?? param.range?.step?.toString() ?? "",
        log: existingConfig?.log ?? false,
        choices:
          existingConfig?.choices?.join(", ") ??
          (param.type === "boolean"
            ? "True, False"
            : param.options?.map((o) => o.value).join(", ")) ??
          "",
      };
    });
    setParamConfigs(newConfigs);
  }, [formData.modelHyperparametersSchema]);

  const deriveHpSpaceFromLocalState = (
    configs: Record<string, ParamSearchConfig>
  ): HPSuggestion[] => {
    const newHpSpace: HPSuggestion[] = [];
    Object.entries(configs).forEach(([paramName, config]) => {
      if (config.enabled) {
        let suggestion: Partial<HPSuggestion> = {
          param_name: paramName,
          suggest_type: config.suggest_type,
        };
        if (config.suggest_type === "categorical") {
          suggestion.choices = config.choices
            ?.split(",")
            .map((s) => {
              const val = s.trim();
              if (val.toLowerCase() === "true") return true;
              if (val.toLowerCase() === "false") return false;
              if (!isNaN(Number(val)) && val.trim() !== "") return Number(val);
              return val;
            })
            .filter((v) => v !== "" && v !== null);
        } else {
          suggestion.low = config.low !== "" ? Number(config.low) : undefined;
          suggestion.high = config.high !== "" ? Number(config.high) : undefined;
          if (config.step !== "") suggestion.step = Number(config.step);
          if (config.log) suggestion.log = true;
        }
        newHpSpace.push(suggestion as HPSuggestion);
      }
    });
    return newHpSpace;
  };

  const handleParamConfigChange = (
    paramName: string,
    field: keyof ParamSearchConfig,
    value: any
  ) => {
    setParamConfigs((prev) => {
      const newConfigs = {
        ...prev,
        [paramName]: { ...prev[paramName], [field]: value },
      };
      const newHpSpace = deriveHpSpaceFromLocalState(newConfigs);
      updateFormData({ hpSpace: newHpSpace });
      return newConfigs;
    });
  };

  if (!formData.modelType) {
    return (
      <Alert variant="default">
        <AlertDescription>
          Please select a model in the previous step to see its hyperparameters.
        </AlertDescription>
      </Alert>
    );
  }

  if (formData.modelHyperparametersSchema.length === 0) {
    return (
      <Alert>
        <AlertDescription>
          No configurable hyperparameters defined for this model. Default settings will be used.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <WandSparkles className="mr-2 h-5 w-5 text-primary" />
          Configure Search Space
        </CardTitle>
        <CardDescription>
          Enable and configure the search range for each hyperparameter of the{" "}
          <strong>{formData.modelDisplayName}</strong> model.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea>
          <div className="space-y-4 pr-3">
            {formData.modelHyperparametersSchema.map((paramDef) => (
              <ParamConfigRow
                key={paramDef.name}
                definition={paramDef}
                config={paramConfigs[paramDef.name]}
                onConfigChange={(field, value) =>
                  handleParamConfigChange(paramDef.name, field, value)
                }
              />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
