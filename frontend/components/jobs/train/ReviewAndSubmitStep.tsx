// frontend/components/jobs/train/ReviewAndSubmitStep.tsx
import React from 'react';
import { TrainingJobFormData } from '@/types/jobs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Database, Brain, ListChecks, TargetIcon, Settings2, FileText } from 'lucide-react';

interface ReviewAndSubmitStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  // isSubmitting prop will be handled by the parent wizard for the final submit button
}

const SectionCard: React.FC<{ title: string; icon?: React.ReactNode; children: React.ReactNode; className?: string }> = ({ title, icon, children, className }) => (
  <Card className={className}>
    <CardHeader className="pb-3 pt-4">
      <CardTitle className="text-base font-semibold flex items-center">
        {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent className="text-sm">
      {children}
    </CardContent>
  </Card>
);

const KeyValueItem: React.FC<{ label: string; value?: string | number | null; badge?: boolean; truncateValue?: boolean }> = ({ label, value, badge, truncateValue }) => (
  <div className="flex justify-between items-start py-1.5 border-b border-dashed last:border-b-0">
    <dt className="text-muted-foreground whitespace-nowrap mr-2">{label}:</dt>
    <dd className={`font-medium text-right ${truncateValue ? 'truncate' : 'break-all'}`} title={String(value ?? 'N/A')}>
      {value === null || value === undefined ? (
        <span className="text-muted-foreground italic">N/A</span>
      ) : badge ? (
        <Badge variant="secondary" className="text-xs">{String(value)}</Badge>
      ) : (
        String(value)
      )}
    </dd>
  </div>
);

export const ReviewAndSubmitStep: React.FC<ReviewAndSubmitStepProps> = ({
  formData,
  updateFormData,
}) => {
  const handleJobNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateFormData({ trainingJobName: e.target.value });
  };
  const handleJobDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateFormData({ trainingJobDescription: e.target.value });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><CheckCircle2 className="mr-2 h-5 w-5 text-primary"/>Review Your Training Job Configuration</CardTitle>
          <CardDescription>
            Please review all settings below. You can go back to previous steps to make changes.
            Provide a name for this training job before submitting.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="trainingJobName" className="text-base">Training Job Name *</Label>
                <Input
                    id="trainingJobName"
                    value={formData.trainingJobName}
                    onChange={handleJobNameChange}
                    placeholder="e.g., DefectModel_DatasetX_RF_V1"
                    className="text-base h-11"
                />
            </div>
             <div className="space-y-2">
                <Label htmlFor="trainingJobDescription" className="text-base">Description (Optional)</Label>
                <Input // Changed to Input for consistency, Textarea can be used if longer descriptions are common
                    id="trainingJobDescription"
                    value={formData.trainingJobDescription || ""}
                    onChange={(e) => updateFormData({ trainingJobDescription: e.target.value })}
                    placeholder="Briefly describe this training job or its purpose."
                />
            </div>
        </CardContent>
      </Card>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SectionCard title="Source Data" icon={<Database />}>
          <dl className="space-y-1">
            <KeyValueItem label="Repository" value={formData.repositoryName || `ID: ${formData.repositoryId}`} />
            <KeyValueItem label="Dataset" value={formData.datasetName || `ID: ${formData.datasetId}`} />
          </dl>
        </SectionCard>

        <SectionCard title="Model Details" icon={<Brain />}>
          <dl className="space-y-1">
            <KeyValueItem label="Base Model Name" value={formData.modelName} />
            <KeyValueItem label="Model Type" value={formData.modelType} badge />
          </dl>
        </SectionCard>
        
        <SectionCard title="Features & Target" icon={<ListChecks />} className="md:col-span-1">
            <KeyValueItem label="Target Column" value={formData.targetColumn} badge />
            <div className="mt-2">
                <Label className="text-xs text-muted-foreground uppercase block mb-1">Selected Features ({formData.selectedFeatures.length})</Label>
                <ScrollArea className="h-24 rounded-md border bg-muted/30 p-2">
                    {formData.selectedFeatures.length > 0 ? (
                        <ul className="list-disc list-inside pl-2 text-xs space-y-0.5">
                            {formData.selectedFeatures.map(f => <li key={f} className="truncate" title={f}>{f}</li>)}
                        </ul>
                    ) : (
                        <p className="text-xs italic text-muted-foreground">No features selected.</p>
                    )}
                </ScrollArea>
            </div>
        </SectionCard>

        <SectionCard title="Hyperparameters" icon={<Settings2 />} className="md:col-span-1">
          {Object.keys(formData.configuredHyperparameters).length > 0 ? (
            <ScrollArea className="h-40 pr-2"> {/* Max height for hyperparams list */}
              <dl className="space-y-1">
                {Object.entries(formData.configuredHyperparameters).map(([key, value]) => (
                  <KeyValueItem key={key} label={key.replace(/_/g, ' ')} value={JSON.stringify(value)} truncateValue />
                ))}
              </dl>
            </ScrollArea>
          ) : (
            <p className="text-sm italic text-muted-foreground">Using model defaults (no overrides configured).</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
};