// frontend/app/jobs/hp-search/page.tsx
"use client";

import React, { useState, useCallback, Suspense, useMemo } from "react";
import { useRouter } from "next/navigation";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageContainer } from "@/components/ui/page-container";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, ArrowRight, Check, Loader2, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { PageLoader } from '@/components/ui/page-loader';
import Link from "next/link";

import { HpSearchJobFormData, initialHpSearchJobFormData } from "@/types/jobs";
import { HPSearchJobCreatePayload } from "@/types/api";

import { HpSearchJobStepper } from "@/components/jobs/hp-search/HpSearchJobStepper";
import { SelectRepositoryAndDatasetStep } from "@/components/jobs/hp-search/SelectRepositoryAndDatasetStep";
import { SelectModelForHpSearchStep } from "@/components/jobs/hp-search/SelectModelForHpSearchStep";
import { ConfigureSearchSpaceStep } from "@/components/jobs/hp-search/ConfigureSearchSpaceStep";
import { ConfigureSearchSettingsStep } from "@/components/jobs/hp-search/ConfigureSearchSettingsStep";
import { ReviewAndSubmitHpSearchStep } from "@/components/jobs/hp-search/ReviewAndSubmitHpSearchStep";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";

const WIZARD_STEPS = [
  { name: "Source Data", description: "Select repository and dataset." },
  { name: "Model", description: "Choose a model architecture." },
  { name: "Search Space", description: "Define hyperparameter ranges." },
  { name: "Search Settings", description: "Configure Optuna's behavior." },
  { name: "Review & Submit", description: "Finalize and start the search." },
];
const TOTAL_STEPS = WIZARD_STEPS.length;

function CreateHpSearchJobPageContent() {
  const router = useRouter();
  const { toast } = useToast();

  const [currentStep, setCurrentStep] = useState(1);
  const [maxCompletedStep, setMaxCompletedStep] = useState(0);
  const [formData, setFormData] = useState<HpSearchJobFormData>(initialHpSearchJobFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const updateFormData = useCallback((updates: Partial<HpSearchJobFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  }, []);

  const handleStepNavigation = (stepNumber: number) => {
    if (stepNumber <= maxCompletedStep + 1 && stepNumber <= TOTAL_STEPS && stepNumber >= 1) {
      setCurrentStep(stepNumber);
    } else {
      toast({
        title: "Navigation Restricted",
        description: "Please complete the current step before navigating.",
        variant: "default",
      });
    }
  };

  const validateStep = (step: number): boolean => {
    switch (step) {
      case 1:
        if (!formData.repositoryId || !formData.datasetId) {
          toast({ title: "Missing Information", description: "Please select both a repository and a dataset.", variant: "destructive" });
          return false;
        }
        return true;
      case 2:
        if (!formData.modelType) {
          toast({ title: "Missing Information", description: "Please select a model type.", variant: "destructive" });
          return false;
        }
        return true;
      case 3:
        if (formData.hpSpace.length === 0) {
          toast({ title: "Empty Search Space", description: "Please enable and configure at least one hyperparameter for the search.", variant: "destructive" });
          return false;
        }
        return true;
      case 4:
         if (!formData.optunaConfig.n_trials || formData.optunaConfig.n_trials < 1) {
          toast({ title: "Invalid Trials", description: "Number of trials must be at least 1.", variant: "destructive" });
          return false;
        }
        return true;
      case 5:
        if (!formData.studyName.trim()) {
          toast({ title: "Study Name Required", description: "Please provide a name for this study.", variant: "destructive" });
          return false;
        }
        if (formData.saveBestModel && !formData.modelBaseName.trim()) {
          toast({ title: "Model Name Required", description: "Please provide a base name for saving the best model.", variant: "destructive" });
          return false;
        }
        return true;
      default:
        return false;
    }
  };

  const isStepValid = useMemo(() => {
    switch (currentStep) {
      case 1: return !!(formData.repositoryId && formData.datasetId);
      case 2: return !!formData.modelType;
      case 3: return formData.hpSpace.length > 0;
      case 4: return !!(formData.optunaConfig.n_trials && formData.optunaConfig.n_trials > 0);
      case 5: return !!(formData.studyName.trim() && (!formData.saveBestModel || formData.modelBaseName.trim()));
      default: return false;
    }
  }, [currentStep, formData]);

  const handleNext = () => {
    if (!validateStep(currentStep)) return;
    if (currentStep < TOTAL_STEPS) {
      setMaxCompletedStep(Math.max(maxCompletedStep, currentStep));
      setCurrentStep(currentStep + 1);
    } else {
      handleSubmitJob();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const handleSubmitJob = async () => {
    if (!validateStep(TOTAL_STEPS)) return;

    setIsSubmitting(true);
    setSubmissionError(null);

    const payload: HPSearchJobCreatePayload = {
      dataset_id: formData.datasetId!,
      optuna_study_name: formData.studyName,
      config: {
        model_name: formData.modelBaseName,
        model_type: formData.modelType!,
        hp_space: formData.hpSpace,
        optuna_config: formData.optunaConfig,
        save_best_model: formData.saveBestModel,
        feature_columns: formData.datasetFeatureSpace, // These are auto-populated when dataset is selected
        target_column: formData.datasetTargetColumn!,
        random_seed: 42,
      },
    };

    try {
      const response = await apiService.post<any, HPSearchJobCreatePayload>("/ml/search", payload);
      toast({
        title: "HP Search Job Submitted",
        description: `Job "${formData.studyName}" submitted. Task ID: ${response.celery_task_id}`,
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/jobs/${response.job_id}?type=hp_search`}>View Job</Link>
          </Button>
        ),
      });
      router.push(`/jobs/${response.job_id}?type=hp_search`);
    } catch (error) {
      const errorMsg = error instanceof ApiError ? error.message : "Failed to submit HP search job.";
      setSubmissionError(errorMsg);
      handleApiError(error, "HP Search Job Submission Failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return <SelectRepositoryAndDatasetStep formData={formData} updateFormData={updateFormData} />;
      case 2: return <SelectModelForHpSearchStep formData={formData} updateFormData={updateFormData} />;
      case 3: return <ConfigureSearchSpaceStep formData={formData} updateFormData={updateFormData} />;
      case 4: return <ConfigureSearchSettingsStep formData={formData} updateFormData={updateFormData} />;
      case 5: return <ReviewAndSubmitHpSearchStep formData={formData} updateFormData={updateFormData} />;
      default: return <div>Invalid Step</div>;
    }
  };

  return (
    <MainLayout>
      <PageContainer
        title="Create New Hyperparameter Search Job"
        description="Follow these steps to configure and launch a new HP search."
      >
        <HpSearchJobStepper currentStep={currentStep} steps={WIZARD_STEPS} onStepClick={handleStepNavigation} maxCompletedStep={maxCompletedStep} />

        <Card className="mt-6">
          <CardContent className="pt-6">
            {renderStepContent()}
          </CardContent>
        </Card>

        {submissionError && (
          <Alert variant="destructive" className="mt-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{submissionError}</AlertDescription>
          </Alert>
        )}

        <div className="mt-8 flex justify-between">
          <Button variant="outline" onClick={handlePrevious} disabled={currentStep === 1 || isSubmitting}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Previous
          </Button>
          <Button onClick={handleNext} disabled={isSubmitting || !isStepValid}>
            {isSubmitting && currentStep === TOTAL_STEPS ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : currentStep === TOTAL_STEPS ? (
              <Check className="mr-2 h-4 w-4" />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" />
            )}
            {currentStep === TOTAL_STEPS ? (isSubmitting ? "Submitting..." : "Submit HP Search Job") : "Next"}
          </Button>
        </div>
      </PageContainer>
    </MainLayout>
  );
}

export default function CreateHpSearchJobPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading HP search form..." />}>
      <CreateHpSearchJobPageContent />
    </Suspense>
  );
}