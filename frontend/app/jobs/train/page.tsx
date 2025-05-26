// frontend/app/jobs/train/page.tsx
"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";  
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { ArrowLeft, Wand2, Database, Cog, Settings, Loader2, AlertCircle, CheckCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";
import { TrainingJobCreatePayload, TrainingConfig, TrainingJobSubmitResponse } from "@/types/api/training-job";
import { ModelTypeEnum, JobStatusEnum } from "@/types/api/enums";
import { TaskResponse } from "@/types/api/task"; // Assuming TaskResponse includes job_id
import { ScrollArea } from "@radix-ui/react-scroll-area";

const API_ENDPOINT_SUBMIT_TRAINING_JOB = "/ml/train";
const API_ENDPOINT_LIST_DATASETS = "/datasets"; // Needs query params for status=ready

function CreateTrainingJobPageContent() {  
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const preselectedDatasetId = searchParams.get("datasetId");
  const preselectedRepoId = searchParams.get("repositoryId"); // For dataset filtering if API supports

  const [formData, setFormData] = useState<Partial<TrainingJobCreatePayload>>({
    dataset_id: preselectedDatasetId ? parseInt(preselectedDatasetId) : undefined,
    config: {
      model_name: "",
      model_type: ModelTypeEnum.SKLEARN_RANDOMFOREST, // Default model type
      hyperparameters: {},
      feature_columns: [], // Will be auto-populated
      target_column: "",   // Will be auto-populated
      random_seed: 42,
      eval_test_split_size: 0.2,
    },
  });
  const [hyperparametersJson, setHyperparametersJson] = useState<string>("{}");

  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [selectedDataset, setSelectedDataset] = useState<DatasetRead | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const availableModelTypes = Object.values(ModelTypeEnum);

  const fetchReadyDatasets = useCallback(async () => {
    setIsLoadingDatasets(true);
    try {
      // Fetch all datasets and filter client-side, or use backend filtering if available.
      // Assuming a backend filter for status=ready for efficiency.
      // If preselectedRepoId exists, you might want to filter by that too.
      const params = new URLSearchParams({ status: "ready", limit: "1000" });
      if (preselectedRepoId) params.append("repository_id", preselectedRepoId);

      const response = await apiService.get<PaginatedDatasetRead>(`${API_ENDPOINT_LIST_DATASETS}?${params.toString()}`);
      setDatasets(response.items || []);

      if (preselectedDatasetId) {
        const foundDataset = response.items?.find(d => d.id === parseInt(preselectedDatasetId));
        if (foundDataset) {
          setSelectedDataset(foundDataset);
          setFormData(prev => ({
            ...prev,
            dataset_id: foundDataset.id,
            config: {
              ...(prev.config as TrainingConfig),
              feature_columns: foundDataset.config.feature_columns,
              target_column: foundDataset.config.target_column,
              model_name: `${foundDataset.name}_model_${Date.now().toString().slice(-4)}`,
            }
          }));
        }
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch datasets");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, [preselectedDatasetId, preselectedRepoId]);

  useEffect(() => {
    fetchReadyDatasets();
  }, [fetchReadyDatasets]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      config: {
        ...(prev.config as TrainingConfig),
        [name]: name === 'random_seed' || name === 'eval_test_split_size' ? (value === '' ? null : Number(value)) : value,
      }
    }));
  };

  const handleDatasetChange = (datasetIdString: string) => {
    const datasetId = parseInt(datasetIdString);
    const foundDataset = datasets.find(d => d.id === datasetId);
    setSelectedDataset(foundDataset || null);

    if (foundDataset) {
      setFormData(prev => ({
        ...prev,
        dataset_id: foundDataset.id,
        config: {
          ...(prev.config as TrainingConfig),
          feature_columns: foundDataset.config.feature_columns,
          target_column: foundDataset.config.target_column,
          model_name: `${foundDataset.name}_model_${Date.now().toString().slice(-4)}`, // Suggest default name
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        dataset_id: undefined,
        config: {
          ...(prev.config as TrainingConfig),
          feature_columns: [],
          target_column: "",
        }
      }));
    }
  };

  const handleModelTypeChange = (modelType: ModelTypeEnum) => {
    setFormData(prev => ({
      ...prev,
      config: {
        ...(prev.config as TrainingConfig),
        model_type: modelType,
        hyperparameters: {}, // Reset HPs when model type changes
      }
    }));
    setHyperparametersJson("{}");
  };

  const handleHyperparametersJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setHyperparametersJson(e.target.value);
    // Basic validation could be done here, or on submit
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formData.dataset_id) {
      setFormError("Please select a dataset.");
      return;
    }
    if (!formData.config?.model_name?.trim()) {
      setFormError("Please provide a model name.");
      return;
    }

    let parsedHyperparameters = {};
    try {
      parsedHyperparameters = JSON.parse(hyperparametersJson);
      if (typeof parsedHyperparameters !== 'object' || parsedHyperparameters === null) {
        throw new Error("Hyperparameters must be a valid JSON object.");
      }
    } catch (jsonError) {
      setFormError("Hyperparameters are not valid JSON. Please check the format.");
      return;
    }

    setIsSubmitting(true);

    const payload: TrainingJobCreatePayload = {
      dataset_id: formData.dataset_id,
      config: {
        ...(formData.config as TrainingConfig),
        hyperparameters: parsedHyperparameters,
      },
    };

    try {
      const response = await apiService.post<TrainingJobSubmitResponse, TrainingJobCreatePayload>(
        API_ENDPOINT_SUBMIT_TRAINING_JOB,
        payload
      );
      toast({
        title: "Training Job Submitted",
        description: `Task ${response.celery_task_id} for job ID ${response.job_id} has been successfully submitted.`, // Assuming job_id is in TaskResponse
        action: response.job_id ? (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/jobs/${response.job_id}?type=training`}>View Job</Link>
            </Button>
          ) : undefined,
      });
      // Redirect to the job details page or a general jobs list
      if (response.job_id) {
        router.push(`/jobs/${response.job_id}?type=training`);
      } else {
        router.push('/jobs?tab=training'); // Fallback to jobs list
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        handleApiError(err, "Failed to submit training job");
        setFormError("An unexpected error occurred.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };


  return (
    <MainLayout>
      <PageContainer
        title="Create New Training Job"
        description="Configure and launch a new model training process."
        actions={
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><Database className="mr-2 h-5 w-5 text-primary" /> Dataset Selection</CardTitle>
              <CardDescription>Choose a "Ready" dataset for training your model.</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingDatasets ? (
                <Skeleton className="h-10 w-full" />
              ) : datasets.length === 0 ? (
                <Alert variant="default">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    No "Ready" datasets found. Please <Link href="/datasets/create" className="font-medium text-primary hover:underline">create a dataset</Link> first or ensure existing datasets are successfully generated.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="dataset_id">Select Dataset</Label>
                  <Select
                    value={formData.dataset_id?.toString() || ""}
                    onValueChange={handleDatasetChange}
                    required
                  >
                    <SelectTrigger id="dataset_id">
                      <SelectValue placeholder="Choose a dataset..." />
                    </SelectTrigger>
                    <SelectContent>
                      {datasets.map((ds) => (
                        <SelectItem key={ds.id} value={ds.id.toString()}>
                          {ds.name} (ID: {ds.id}, Rows: {ds.num_rows ?? 'N/A'})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </CardContent>
          </Card>

          {selectedDataset && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center"><Wand2 className="mr-2 h-5 w-5 text-primary" /> Model Configuration</CardTitle>
                  <CardDescription>Define the model name, type, and its hyperparameters.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="model_name">Model Name</Label>
                    <Input
                      id="model_name"
                      name="model_name"
                      value={formData.config?.model_name || ""}
                      onChange={handleInputChange}
                      placeholder="e.g., MyRandomForest_Classifier_V1"
                      required
                    />
                    <p className="text-xs text-muted-foreground">A descriptive name for your trained model.</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="model_type">Model Type</Label>
                    <Select
                      value={formData.config?.model_type || ""}
                      onValueChange={(value) => handleModelTypeChange(value as ModelTypeEnum)}
                    >
                      <SelectTrigger id="model_type">
                        <SelectValue placeholder="Select model type..." />
                      </SelectTrigger>
                      <SelectContent>
                        {availableModelTypes.map((type) => (
                          <SelectItem key={type} value={type}>{type}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="hyperparameters">Hyperparameters (JSON format)</Label>
                    <Textarea
                      id="hyperparameters"
                      name="hyperparameters"
                      value={hyperparametersJson}
                      onChange={handleHyperparametersJsonChange}
                      placeholder={'{\n  "n_estimators": 100,\n  "max_depth": 10\n}'}
                      rows={6}
                      className="font-mono text-xs"
                    />
                    <p className="text-xs text-muted-foreground">
                      Enter hyperparameters as a JSON object. Leave empty for model defaults.
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center"><Cog className="mr-2 h-5 w-5 text-primary"/> Feature & Target Settings</CardTitle>
                  <CardDescription>Review features and target from the selected dataset.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label>Feature Columns ({formData.config?.feature_columns?.length || 0} selected)</Label>
                    <ScrollArea className="h-24 mt-1 rounded-md border p-2 text-xs bg-muted/50">
                      {formData.config?.feature_columns && formData.config.feature_columns.length > 0 ? (
                        <ul className="list-disc list-inside pl-2">
                          {formData.config.feature_columns.map(fc => <li key={fc} className="truncate" title={fc}>{fc}</li>)}
                        </ul>
                      ) : <p className="text-muted-foreground italic">Select a dataset to see features.</p>}
                    </ScrollArea>
                     <p className="text-xs text-muted-foreground mt-1">These features from the dataset configuration will be used for training.</p>
                  </div>
                   <div>
                    <Label>Target Column</Label>
                    <Input value={formData.config?.target_column || ""} readOnly className="mt-1 bg-muted/50"/>
                    <p className="text-xs text-muted-foreground mt-1">This target column from the dataset configuration will be used.</p>
                  </div>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center"><Settings className="mr-2 h-5 w-5 text-primary"/> Advanced Settings (Optional)</CardTitle>
                </CardHeader>
                <CardContent className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="random_seed">Random Seed</Label>
                    <Input
                      id="random_seed"
                      name="random_seed"
                      type="number"
                      value={formData.config?.random_seed ?? ""}
                      onChange={handleInputChange}
                      placeholder="e.g., 42"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="eval_test_split_size">Evaluation Test Split Size</Label>
                    <Input
                      id="eval_test_split_size"
                      name="eval_test_split_size"
                      type="number"
                      step="0.01"
                      min="0.05"
                      max="0.95"
                      value={formData.config?.eval_test_split_size ?? ""}
                      onChange={handleInputChange}
                      placeholder="e.g., 0.2"
                    />
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {formError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !selectedDataset || isLoadingDatasets} size="lg">
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting Job...
                </>
              ) : (
                <>
                  <Wand2 className="mr-2 h-4 w-4" /> Start Training Job
                </>
              )}
            </Button>
          </div>
        </form>
      </PageContainer>
    </MainLayout>
  );
}

export default function CreateTrainingJobPage() { // New wrapper component
  return (
    <Suspense fallback={<div>Loading page data...</div>}>
      <CreateTrainingJobPageContent />
    </Suspense>
  );
}