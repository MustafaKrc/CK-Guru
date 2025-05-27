// frontend/components/jobs/train/ReviewAndSubmitStep.tsx
import React from 'react';
import { TrainingJobFormData } from '@/types/jobs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Database, Brain, ListChecks, TargetIcon, Settings2, FileText } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';

interface ReviewAndSubmitStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
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

const KeyValueItem: React.FC<{ label: string; value?: string | number | null | boolean; badge?: boolean; truncateValue?: boolean }> = ({ label, value, badge, truncateValue }) => (
  <div className="flex justify-between items-start py-1.5 border-b border-dashed last:border-b-0">
    <dt className="text-muted-foreground whitespace-nowrap mr-2">{label}:</dt>
    <dd className={`font-medium text-right ${truncateValue ? 'truncate' : 'break-all'}`} title={String(value ?? 'N/A')}>
      {value === null || value === undefined ? (
        <span className="text-muted-foreground italic">N/A</span>
      ) : badge ? (
        <Badge variant="secondary" className="text-xs">{String(value)}</Badge>
      ) : typeof value === 'boolean' ? (
        <Badge variant={value ? "default" : "outline"} className="text-xs">{value ? "Yes" : "No"}</Badge>
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
  const handleModelBaseNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateFormData({ modelBaseName: e.target.value });
  };
  const handleJobDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateFormData({ trainingJobDescription: e.target.value });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><CheckCircle2 className="mr-2 h-5 w-5 text-primary"/>Review & Submit Training Job</CardTitle>
          <CardDescription>
            Review all settings. Provide a name for this job and a base name for the new model that will be created.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="trainingJobName" className="text-sm">Training Job Name *</Label>
                    <Input
                        id="trainingJobName"
                        value={formData.trainingJobName}
                        onChange={handleJobNameChange}
                        placeholder="e.g., Experiment_MainDataset_RF_V1"
                        className="h-10"
                    />
                </div>
                 <div className="space-y-1.5">
                    <Label htmlFor="modelBaseName" className="text-sm">New Model Base Name *</Label>
                    <Input
                        id="modelBaseName"
                        value={formData.modelBaseName}
                        onChange={handleModelBaseNameChange}
                        placeholder="e.g., Main_RF_Classifier"
                        className="h-10"
                    />
                     <p className="text-xs text-muted-foreground">A version number will be appended by the system (e.g., _v1).</p>
                </div>
            </div>
             <div className="space-y-1.5">
                <Label htmlFor="trainingJobDescription" className="text-sm">Job Description (Optional)</Label>
                <Textarea
                    id="trainingJobDescription"
                    value={formData.trainingJobDescription || ""}
                    onChange={handleJobDescriptionChange}
                    placeholder="Briefly describe this training job or its purpose."
                    rows={2}
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

        <SectionCard title="Model Configuration" icon={<Brain />}>
          <dl className="space-y-1">
            {/* Model Base Name is now an input above, so we can display what's entered */}
            <KeyValueItem label="New Model Name (Base)" value={formData.modelBaseName || "Not set"} />
            <KeyValueItem label="Model Type" value={formData.modelDisplayName || formData.modelType} badge />
          </dl>
        </SectionCard>
        
        <SectionCard title="Features & Target" icon={<ListChecks />} className="md:col-span-1">
            <KeyValueItem label="Target Column" value={formData.trainingTargetColumn} badge />
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
            <ScrollArea className="h-40 pr-2">
              <dl className="space-y-1">
                {Object.entries(formData.configuredHyperparameters).map(([key, value]) => (
                  <KeyValueItem key={key} label={key.replace(/_/g, ' ')} value={value} truncateValue />
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