// frontend/components/jobs/hp-search/ConfigureSearchSettingsStep.tsx
"use client";

import React from "react";
import { HpSearchJobFormData } from "@/types/jobs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { SlidersHorizontal, HelpCircle } from "lucide-react";
import { ObjectiveMetricEnum, SamplerTypeEnum, PrunerTypeEnum } from "@/types/api/enums";

interface ConfigureSearchSettingsStepProps {
  formData: HpSearchJobFormData;
  updateFormData: (updates: Partial<HpSearchJobFormData>) => void;
}

export const ConfigureSearchSettingsStep: React.FC<ConfigureSearchSettingsStepProps> = ({
  formData,
  updateFormData,
}) => {
  const handleOptunaConfigChange = (
    field: keyof HpSearchJobFormData["optunaConfig"],
    value: any
  ) => {
    updateFormData({
      optunaConfig: {
        ...formData.optunaConfig,
        [field]: value,
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <SlidersHorizontal className="mr-2 h-5 w-5 text-primary" />
          Search Settings
        </CardTitle>
        <CardDescription>
          Configure the behavior of the Optuna hyperparameter search process.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
          {/* Number of Trials */}
          <div className="space-y-2">
            <Label htmlFor="n_trials">Number of Trials *</Label>
            <Input
              id="n_trials"
              type="number"
              min="1"
              value={formData.optunaConfig.n_trials}
              onChange={(e) =>
                handleOptunaConfigChange("n_trials", parseInt(e.target.value, 10) || 1)
              }
              className="h-9"
            />
          </div>

          {/* Objective Metric */}
          <div className="space-y-2">
            <Label htmlFor="objective_metric">Objective Metric *</Label>
            <Select
              value={formData.optunaConfig.objective_metric}
              onValueChange={(value) =>
                handleOptunaConfigChange("objective_metric", value as ObjectiveMetricEnum)
              }
            >
              <SelectTrigger id="objective_metric" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.values(ObjectiveMetricEnum).map((metric) => (
                  <SelectItem key={metric} value={metric}>
                    {metric.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Sampler Type */}
          <div className="space-y-2">
            <Label htmlFor="sampler_type" className="flex items-center">
              Sampler Type *
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3.5 w-3.5 ml-1.5 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Algorithm for sampling hyperparameters. TPE is generally recommended.</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </Label>
            <Select
              value={formData.optunaConfig.sampler_type}
              onValueChange={(value) =>
                handleOptunaConfigChange("sampler_type", value as SamplerTypeEnum)
              }
            >
              <SelectTrigger id="sampler_type" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.values(SamplerTypeEnum).map((sampler) => (
                  <SelectItem key={sampler} value={sampler}>
                    {sampler.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Pruner Type */}
          <div className="space-y-2">
            <Label htmlFor="pruner_type" className="flex items-center">
              Pruner Type *
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3.5 w-3.5 ml-1.5 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      Algorithm for early-stopping unpromising trials. Median is a good default.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </Label>
            <Select
              value={formData.optunaConfig.pruner_type}
              onValueChange={(value) =>
                handleOptunaConfigChange("pruner_type", value as PrunerTypeEnum)
              }
            >
              <SelectTrigger id="pruner_type" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.values(PrunerTypeEnum).map((pruner) => (
                  <SelectItem key={pruner} value={pruner}>
                    {pruner.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* CV Folds */}
          <div className="space-y-2">
            <Label htmlFor="hp_search_cv_folds">Cross-Validation Folds</Label>
            <Input
              id="hp_search_cv_folds"
              type="number"
              min="2"
              value={formData.optunaConfig.hp_search_cv_folds ?? ""}
              onChange={(e) =>
                handleOptunaConfigChange(
                  "hp_search_cv_folds",
                  e.target.value === "" ? null : parseInt(e.target.value)
                )
              }
              className="h-9"
              placeholder="Default: 3"
            />
          </div>
        </div>

        {/* Other Options */}
        <div className="space-y-4 pt-4 border-t">
          <div className="flex items-center space-x-3">
            <Switch
              id="continue_if_exists"
              checked={formData.optunaConfig.continue_if_exists}
              onCheckedChange={(checked) => handleOptunaConfigChange("continue_if_exists", checked)}
            />
            <Label htmlFor="continue_if_exists" className="cursor-pointer">
              Continue study if one with the same name exists
            </Label>
          </div>
          <Alert variant="default" className="text-xs">
            <AlertDescription>
              Enabling this will resume a study if the name matches an existing one. The dataset and
              model type must also match. If disabled, a unique study name is required.
            </AlertDescription>
          </Alert>
        </div>
      </CardContent>
    </Card>
  );
};
