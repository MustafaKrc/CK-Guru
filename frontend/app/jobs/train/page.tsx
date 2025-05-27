// frontend/app/jobs/train/page.tsx
"use client";

import React, { useState, useCallback, Suspense } from "react";
import { useRouter } // , useSearchParams // if needed for initial params
from "next/navigation";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageContainer } from "@/components/ui/page-container";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ArrowLeft, ArrowRight, Check, Link, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { PageLoader } from '@/components/ui/page-loader';

import { TrainingJobFormData, initialTrainingJobFormData } from "@/types/jobs";
import { TrainingJobStepper } from "@/components/jobs/train/TrainingJobStepper";
import { SelectRepositoryAndDatasetStep } from "@/components/jobs/train/SelectRepositoryAndDatasetStep";
import { SelectModelStep } from "@/components/jobs/train/SelectModelStep";
import { ConfigureHyperparametersStep } from "@/components/jobs/train/ConfigureHyperparametersStep";
import { ConfigureFeaturesTargetStep } from "@/components/jobs/train/ConfigureFeaturesTargetStep";
import { ReviewAndSubmitStep } from "@/components/jobs/train/ReviewAndSubmitStep";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { TrainingJobCreatePayload, TrainingJobSubmitResponse } from "@/types/api/training-job";


const WIZARD_STEPS = [
  { name: "Source Data", description: "Select repository and dataset." },
  { name: "Model", description: "Choose a model type." },
  { name: "Hyperparameters", description: "Configure model hyperparameters." },
  { name: "Features & Target", description: "Set features and target variable." },
  { name: "Review & Submit", description: "Finalize and start training." },
];
const TOTAL_STEPS = WIZARD_STEPS.length;

function CreateTrainingJobPageContent() {
  const router = useRouter();
  const { toast } = useToast();

  const [currentStep, setCurrentStep] = useState(1);
  const [maxCompletedStep, setMaxCompletedStep] = useState(0);
  const [formData, setFormData] = useState<TrainingJobFormData>(initialTrainingJobFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const updateFormData = useCallback((updates: Partial<TrainingJobFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  }, []);

  const validateStep = (step: number): boolean => {
    // Basic validation logic for each step
    // More detailed validation should happen within each step component or on "Next"
    switch (step) {
      case 1: // Repository & Dataset
        return !!formData.repositoryId && !!formData.datasetId;
      case 2: // Model
        return !!formData.modelId && !!formData.modelType && !!formData.modelName;
      case 3: // Hyperparameters
        // Validation can be complex here, e.g., ensuring required HPs are set if schema indicates
        return true; // For now, assume valid or validated within step
      case 4: // Features & Target
        return formData.selectedFeatures.length > 0 && !!formData.targetColumn;
      case 5: // Review & Submit (Job Name)
        return formData.trainingJobName.trim() !== "";
      default:
        return false;
    }
  };
  
  const handleStepNavigation = (stepNumber: number) => {
    if (stepNumber <= maxCompletedStep + 1 && stepNumber <= TOTAL_STEPS && stepNumber >= 1) {
        setCurrentStep(stepNumber);
    } else {
        toast({
            title: "Navigation Restricted",
            description: "Please complete the current step before navigating to a future step.",
            variant: "default",
        });
    }
  };

  const handleNext = () => {
    if (!validateStep(currentStep)) {
      toast({
        title: "Validation Error",
        description: WIZARD_STEPS[currentStep - 1].description + " is not fully configured.",
        variant: "destructive",
      });
      return;
    }
    if (currentStep < TOTAL_STEPS) {
      setMaxCompletedStep(Math.max(maxCompletedStep, currentStep));
      setCurrentStep(currentStep + 1);
    } else {
      // This is the final "Submit" action
      handleSubmitTrainingJob();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmitTrainingJob = async () => {
    if (!validateStep(TOTAL_STEPS)) {
        toast({ title: "Validation Error", description: "Please provide a name for the training job.", variant: "destructive" });
        return;
    }
    setIsSubmitting(true);
    setSubmissionError(null);

    const payload: TrainingJobCreatePayload = {
      dataset_id: formData.datasetId!, // Assert non-null as validated
      training_job_name: formData.trainingJobName,
      training_job_description: formData.trainingJobDescription || null,
      model_base_name: formData.modelName!, // Backend will handle versioning
      model_type: formData.modelType!,
      hyperparameters: formData.configuredHyperparameters,
      feature_columns: formData.selectedFeatures,
      target_column: formData.targetColumn!,
      random_seed: formData.randomSeed ?? 42, // Default if not in formData.config
      eval_test_split_size: formData.evalTestSplitSize ?? 0.2, // Default if not in formData.config
    };
    
    try {
      const response = await apiService.submitTrainingJob(payload);
      toast({
        title: "Training Job Submitted",
        description: `Job "${formData.trainingJobName}" (ID: ${response.job_id}) created. Task ID: ${response.celery_task_id}`,
        variant: "default",
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/jobs/${response.job_id}?type=training`}>View Job</Link>
          </Button>
        ),
      });
      router.push(`/jobs/${response.job_id}?type=training`);
    } catch (error) {
      const errorMsg = error instanceof ApiError ? error.message : "Failed to submit training job.";
      setSubmissionError(errorMsg);
      handleApiError(error, "Training Job Submission Failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <SelectRepositoryAndDatasetStep formData={formData} updateFormData={updateFormData} onStepComplete={() => { /* Step completion handled by Next button */ }} />;
      case 2:
        return <SelectModelStep formData={formData} updateFormData={updateFormData} onStepComplete={() => {}} />;
      case 3:
        return <ConfigureHyperparametersStep formData={formData} updateFormData={updateFormData} onStepComplete={() => {}} />;
      case 4:
        return <ConfigureFeaturesTargetStep formData={formData} updateFormData={updateFormData} onStepComplete={() => {}} />;
      case 5:
        return <ReviewAndSubmitStep formData={formData} updateFormData={updateFormData} />;
      default:
        return <div>Invalid Step</div>;
    }
  };

  return (
    <MainLayout>
      <PageContainer
        title="Create New Training Job"
        description="Follow these steps to configure and launch a new model training process."
      >
        <TrainingJobStepper currentStep={currentStep} steps={WIZARD_STEPS} onStepClick={handleStepNavigation} maxCompletedStep={maxCompletedStep} />

        <Card className="mt-6">
          <CardContent className="pt-6">
            {renderStepContent()}
          </CardContent>
        </Card>

        {submissionError && (
            <Alert variant="destructive" className="mt-4">
                <AlertDescription>{submissionError}</AlertDescription>
            </Alert>
        )}

        <div className="mt-8 flex justify-between">
          <Button variant="outline" onClick={handlePrevious} disabled={currentStep === 1 || isSubmitting}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Previous
          </Button>
          <Button onClick={handleNext} disabled={isSubmitting || !validateStep(currentStep)}>
            {isSubmitting && currentStep === TOTAL_STEPS ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : currentStep === TOTAL_STEPS ? (
              <Check className="mr-2 h-4 w-4" />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" />
            )}
            {currentStep === TOTAL_STEPS ? (isSubmitting ? "Submitting..." : "Submit Training Job") : "Next"}
          </Button>
        </div>
      </PageContainer>
    </MainLayout>
  );
}

export default function CreateTrainingJobPage() {
  return (
    // Suspense for client components that might fetch data on their own or use hooks like useSearchParams
    <Suspense fallback={<PageLoader message="Loading training job setup..." />}>
      <CreateTrainingJobPageContent />
    </Suspense>
  );
}