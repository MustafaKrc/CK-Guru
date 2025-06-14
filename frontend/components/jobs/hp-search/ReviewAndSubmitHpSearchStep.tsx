// frontend/components/jobs/hp-search/ReviewAndSubmitHpSearchStep.tsx
import React from "react";
import { HpSearchJobFormData } from "@/types/jobs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  Database,
  Brain,
  WandSparkles,
  SlidersHorizontal,
  Settings2,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";

interface ReviewAndSubmitHpSearchStepProps {
  formData: HpSearchJobFormData;
  updateFormData: (updates: Partial<HpSearchJobFormData>) => void;
}

const SectionCard: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, icon, children, className }) => (
  <Card className={className}>
    <CardHeader className="pb-3 pt-4">
      <CardTitle className="text-base font-semibold flex items-center">
        {icon}
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent className="text-sm">{children}</CardContent>
  </Card>
);

const KeyValueItem: React.FC<{ label: string; value?: string | number | boolean }> = ({
  label,
  value,
}) => (
  <div className="flex justify-between items-center py-1 border-b border-dashed last:border-b-0">
    <dt className="text-muted-foreground text-xs">{label}:</dt>
    <dd className="font-medium text-xs break-all text-right">{String(value)}</dd>
  </div>
);

export const ReviewAndSubmitHpSearchStep: React.FC<ReviewAndSubmitHpSearchStepProps> = ({
  formData,
  updateFormData,
}) => {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <CheckCircle2 className="mr-2 h-5 w-5 text-primary" />
            Review & Submit
          </CardTitle>
          <CardDescription>
            Review all configurations below before submitting the HP search job.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="studyName">Study Name *</Label>
              <Input
                id="studyName"
                value={formData.studyName}
                onChange={(e) => updateFormData({ studyName: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label
                htmlFor="modelBaseName"
                className={!formData.saveBestModel ? "text-muted-foreground" : ""}
              >
                Base Name for Best Model *
              </Label>
              <Input
                id="modelBaseName"
                value={formData.modelBaseName}
                onChange={(e) => updateFormData({ modelBaseName: e.target.value })}
                disabled={!formData.saveBestModel}
              />
            </div>
          </div>
          <div className="flex items-center space-x-2 pt-2">
            <Switch
              id="saveBestModel"
              checked={formData.saveBestModel}
              onCheckedChange={(checked) => updateFormData({ saveBestModel: checked })}
            />
            <Label htmlFor="saveBestModel">Save the best model found during the search</Label>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <SectionCard title="Data & Model" icon={<Database className="mr-2 h-4 w-4 text-primary" />}>
          <KeyValueItem label="Repository" value={formData.repositoryName} />
          <KeyValueItem label="Dataset" value={formData.datasetName} />
          <Separator className="my-2" />
          <KeyValueItem label="Model Type" value={formData.modelDisplayName} />
        </SectionCard>

        <SectionCard
          title="Search Space"
          icon={<WandSparkles className="mr-2 h-4 w-4 text-primary" />}
        >
          <ScrollArea className="h-32 pr-2">
            <dl className="space-y-2">
              {formData.hpSpace.map((s) => (
                <div key={s.param_name} className="text-xs">
                  <dt className="font-semibold">{s.param_name}</dt>
                  <dd className="pl-2 text-muted-foreground">
                    {s.suggest_type}: {s.choices ? s.choices.join(", ") : `${s.low} - ${s.high}`}
                    {s.step ? ` (step ${s.step})` : ""}
                    {s.log ? " (log)" : ""}
                  </dd>
                </div>
              ))}
            </dl>
          </ScrollArea>
        </SectionCard>

        <SectionCard
          title="Search Settings"
          icon={<SlidersHorizontal className="mr-2 h-4 w-4 text-primary" />}
        >
          <KeyValueItem label="Trials" value={formData.optunaConfig.n_trials} />
          <KeyValueItem label="Objective" value={formData.optunaConfig.objective_metric} />
          <KeyValueItem label="Sampler" value={formData.optunaConfig.sampler_type} />
          <KeyValueItem label="Pruner" value={formData.optunaConfig.pruner_type} />
          <KeyValueItem
            label="CV Folds"
            value={formData.optunaConfig.hp_search_cv_folds ?? "Default"}
          />
        </SectionCard>
      </div>
    </div>
  );
};
