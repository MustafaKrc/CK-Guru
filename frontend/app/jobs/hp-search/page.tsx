// frontend/app/jobs/hp-search/page.tsx
"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";  
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { ArrowLeft, Wand2, Database, Cog, Settings, Loader2, AlertCircle, CheckCircle, SearchCode, SlidersHorizontal, BarChartHorizontal, FlaskConical, Lightbulb, ListChecks } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";
import { 
    HPSearchJobCreatePayload, HPSearchConfig, OptunaConfig, HPSuggestion, HPSearchJobSubmitResponse 
} from "@/types/api/hp-search-job";
import { ModelTypeEnum, ObjectiveMetricEnum, SamplerTypeEnum, PrunerTypeEnum } from "@/types/api/enums";
import { ScrollArea } from "@/components/ui/scroll-area";

const API_ENDPOINT_SUBMIT_HP_SEARCH_JOB = "/ml/search";
const API_ENDPOINT_LIST_DATASETS = "/datasets";

function CreateHpSearchJobPageContent() {  
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const preselectedDatasetId = searchParams.get("datasetId");

  const initialFormData: HPSearchJobCreatePayload = {
    dataset_id: preselectedDatasetId ? parseInt(preselectedDatasetId) : 0, // Placeholder, will be validated
    optuna_study_name: "",
    config: {
      model_name: "best_model_from_search", // Default model name if saved
      model_type: ModelTypeEnum.SKLEARN_RANDOMFOREST,
      hp_space: [], // To be filled via JSON textarea
      optuna_config: {
        n_trials: 20,
        objective_metric: ObjectiveMetricEnum.F1_WEIGHTED,
        sampler_type: SamplerTypeEnum.TPE,
        pruner_type: PrunerTypeEnum.MEDIAN,
        continue_if_exists: false,
        hp_search_cv_folds: 3,
      },
      save_best_model: true,
      feature_columns: [], // Auto-populated from dataset
      target_column: "",   // Auto-populated from dataset
      random_seed: 42,
    },
  };

  const [formData, setFormData] = useState<HPSearchJobCreatePayload>(initialFormData);
  const [hpSpaceJson, setHpSpaceJson] = useState<string>("[]"); // For HPSuggestion array

  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [selectedDataset, setSelectedDataset] = useState<DatasetRead | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const availableModelTypes = Object.values(ModelTypeEnum);
  const availableObjectiveMetrics = Object.values(ObjectiveMetricEnum);
  const availableSamplerTypes = Object.values(SamplerTypeEnum);
  const availablePrunerTypes = Object.values(PrunerTypeEnum);

  const fetchReadyDatasets = useCallback(async () => {
    setIsLoadingDatasets(true);
    try {
      const params = new URLSearchParams({ status: "ready", limit: "1000" });
      const response = await apiService.get<PaginatedDatasetRead>(`${API_ENDPOINT_LIST_DATASETS}?${params.toString()}`);
      setDatasets(response.items || []);

      if (preselectedDatasetId) {
        const foundDataset = response.items?.find(d => d.id === parseInt(preselectedDatasetId));
        if (foundDataset) {
          setSelectedDataset(foundDataset);
          setFormData(prev => ({
            ...prev,
            dataset_id: foundDataset.id,
            optuna_study_name: `${foundDataset.name}_hp_study_${Date.now().toString().slice(-4)}`,
            config: {
              ...prev.config,
              feature_columns: foundDataset.config.feature_columns,
              target_column: foundDataset.config.target_column,
            }
          }));
        }
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch datasets");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, [preselectedDatasetId]);

  useEffect(() => {
    fetchReadyDatasets();
  }, [fetchReadyDatasets]);

  const handleInputChange = (path: string, value: any) => {
    setFormData(prev => {
      const keys = path.split('.');
      let current = prev as any;
      keys.forEach((key, index) => {
        if (index === keys.length - 1) {
          current[key] = value;
        } else {
          if (!current[key]) current[key] = {};
          current = current[key];
        }
      });
      return { ...prev };
    });
  };

  const handleDatasetChange = (datasetIdString: string) => {
    const datasetId = parseInt(datasetIdString);
    const foundDataset = datasets.find(d => d.id === datasetId);
    setSelectedDataset(foundDataset || null);

    if (foundDataset) {
      setFormData(prev => ({
        ...prev,
        dataset_id: foundDataset.id,
        optuna_study_name: `${foundDataset.name}_hp_study_${Date.now().toString().slice(-4)}`,
        config: {
          ...prev.config,
          feature_columns: foundDataset.config.feature_columns,
          target_column: foundDataset.config.target_column,
        }
      }));
    } else {
       setFormData(prev => ({
        ...prev,
        dataset_id: 0, // Or handle invalid selection appropriately
        config: {
          ...prev.config,
          feature_columns: [],
          target_column: "",
        }
      }));
    }
  };
  
  const handleHpSpaceJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setHpSpaceJson(e.target.value);
  };


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formData.dataset_id || formData.dataset_id === 0) {
      setFormError("Please select a dataset.");
      return;
    }
    if (!formData.optuna_study_name.trim()) {
      setFormError("Please provide a study name.");
      return;
    }
    if (!formData.config.model_name.trim()) {
        setFormError("Please provide a base model name for saving the best model.");
        return;
    }

    let parsedHpSpace: HPSuggestion[] = [];
    try {
      parsedHpSpace = JSON.parse(hpSpaceJson);
      if (!Array.isArray(parsedHpSpace)) {
        throw new Error("HP Space must be a valid JSON array of suggestion objects.");
      }
      // TODO: Add deeper validation for HPSuggestion structure if needed
    } catch (jsonError) {
      setFormError("Hyperparameter Space (HP Space) is not valid JSON. Please check the format.");
      return;
    }

    setIsSubmitting(true);

    const payload: HPSearchJobCreatePayload = {
      ...formData,
      config: {
        ...formData.config,
        hp_space: parsedHpSpace,
      },
    };

    try {
      const response = await apiService.post<HPSearchJobSubmitResponse, HPSearchJobCreatePayload>(
        API_ENDPOINT_SUBMIT_HP_SEARCH_JOB,
        payload
      );
      toast({
        title: "HP Search Job Submitted",
        description: `Task ${response.celery_task_id} for job ID ${response.job_id} has been successfully submitted.`,
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/jobs/${response.job_id}?type=hp_search`}>View Job</Link>
          </Button>
        ),
      });
      router.push(`/jobs/${response.job_id}?type=hp_search`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        handleApiError(err, "Failed to submit HP search job");
        setFormError("An unexpected error occurred.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };


  return (
    <MainLayout>
      <PageContainer
        title="Create New Hyperparameter Search Job"
        description="Configure and launch an Optuna-powered hyperparameter search."
        actions={
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Dataset Selection Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><Database className="mr-2 h-5 w-5 text-primary" /> Dataset & Study Setup</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoadingDatasets ? (
                <Skeleton className="h-10 w-full" />
              ) : datasets.length === 0 ? (
                <Alert variant="default">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    No "Ready" datasets found. Please <Link href="/datasets/create" className="font-medium text-primary hover:underline">create a dataset</Link> first.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="dataset_id">Select Dataset *</Label>
                  <Select
                    value={formData.dataset_id?.toString() || ""}
                    onValueChange={handleDatasetChange}
                    required
                  >
                    <SelectTrigger id="dataset_id"><SelectValue placeholder="Choose a dataset..." /></SelectTrigger>
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
              <div className="space-y-2">
                <Label htmlFor="optuna_study_name">Optuna Study Name *</Label>
                <Input
                  id="optuna_study_name"
                  name="optuna_study_name"
                  value={formData.optuna_study_name}
                  onChange={(e) => handleInputChange('optuna_study_name', e.target.value)}
                  placeholder="e.g., my_randomforest_study_v1"
                  required
                />
              </div>
            </CardContent>
          </Card>

          {selectedDataset && (
            <>
              {/* Model and HP Space Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center"><Wand2 className="mr-2 h-5 w-5 text-primary" /> Model & Hyperparameter Space</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="config.model_name">Base Model Name (for saving best) *</Label>
                    <Input
                      id="config.model_name"
                      name="config.model_name"
                      value={formData.config.model_name}
                      onChange={(e) => handleInputChange('config.model_name', e.target.value)}
                      placeholder="e.g., BestRF_from_search"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="config.model_type">Model Type *</Label>
                    <Select
                      value={formData.config.model_type}
                      onValueChange={(value) => handleInputChange('config.model_type', value as ModelTypeEnum)}
                    >
                      <SelectTrigger id="config.model_type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {availableModelTypes.map((type) => (
                          <SelectItem key={type} value={type}>{type}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="hp_space">Hyperparameter Space (HP Space - JSON array) *</Label>
                    <Textarea
                      id="hp_space"
                      name="hp_space"
                      value={hpSpaceJson}
                      onChange={handleHpSpaceJsonChange}
                      placeholder='[{"param_name": "n_estimators", "suggest_type": "int", "low": 50, "high": 200, "step": 10}, ...]'
                      rows={8}
                      className="font-mono text-xs"
                      required
                    />
                    <p className="text-xs text-muted-foreground">
                      Define parameters to search. Each object needs `param_name`, `suggest_type` (`int`, `float`, `categorical`), and relevant bounds/choices.
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Optuna Configuration Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center"><SlidersHorizontal className="mr-2 h-5 w-5 text-primary" /> Optuna Configuration</CardTitle>
                </CardHeader>
                <CardContent className="grid md:grid-cols-2 gap-x-6 gap-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="config.optuna_config.n_trials">Number of Trials *</Label>
                    <Input id="config.optuna_config.n_trials" name="config.optuna_config.n_trials" type="number" min="1"
                           value={formData.config.optuna_config.n_trials}
                           onChange={(e) => handleInputChange('config.optuna_config.n_trials', parseInt(e.target.value))} required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="config.optuna_config.objective_metric">Objective Metric *</Label>
                    <Select value={formData.config.optuna_config.objective_metric} onValueChange={(v) => handleInputChange('config.optuna_config.objective_metric', v as ObjectiveMetricEnum)}>
                      <SelectTrigger id="config.optuna_config.objective_metric"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {availableObjectiveMetrics.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                   <div className="space-y-2">
                    <Label htmlFor="config.optuna_config.hp_search_cv_folds">CV Folds for HP Search</Label>
                    <Input id="config.optuna_config.hp_search_cv_folds" name="config.optuna_config.hp_search_cv_folds" type="number" min="2"
                           value={formData.config.optuna_config.hp_search_cv_folds ?? ""}
                           onChange={(e) => handleInputChange('config.optuna_config.hp_search_cv_folds', e.target.value === '' ? null : parseInt(e.target.value))} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="config.random_seed">Global Random Seed (Optional)</Label>
                    <Input id="config.random_seed" name="config.random_seed" type="number"
                           value={formData.config.random_seed ?? ""}
                           onChange={(e) => handleInputChange('config.random_seed', e.target.value === '' ? null : parseInt(e.target.value))} />
                  </div>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader><CardTitle className="flex items-center"><Cog className="mr-2 h-5 w-5 text-primary"/>Samplers & Pruners</CardTitle></CardHeader>
                <CardContent className="grid md:grid-cols-2 gap-x-6 gap-y-4">
                   <div className="space-y-2">
                    <Label htmlFor="config.optuna_config.sampler_type">Sampler Type *</Label>
                    <Select value={formData.config.optuna_config.sampler_type} onValueChange={(v) => handleInputChange('config.optuna_config.sampler_type', v as SamplerTypeEnum)}>
                      <SelectTrigger id="config.optuna_config.sampler_type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {availableSamplerTypes.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="config.optuna_config.pruner_type">Pruner Type *</Label>
                    <Select value={formData.config.optuna_config.pruner_type} onValueChange={(v) => handleInputChange('config.optuna_config.pruner_type', v as PrunerTypeEnum)}>
                      <SelectTrigger id="config.optuna_config.pruner_type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {availablePrunerTypes.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                   {/* TODO: Add Textareas for Sampler/Pruner Config JSON if needed */}
                </CardContent>
              </Card>

              {/* Other Options Card */}
              <Card>
                <CardHeader><CardTitle className="flex items-center"><Settings className="mr-2 h-5 w-5 text-primary"/>Other Options</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center space-x-2">
                        <Checkbox id="config.optuna_config.continue_if_exists" 
                                  checked={formData.config.optuna_config.continue_if_exists} 
                                  onCheckedChange={(checked) => handleInputChange('config.optuna_config.continue_if_exists', !!checked)} />
                        <Label htmlFor="config.optuna_config.continue_if_exists" className="text-sm font-normal">Continue study if exists (must match dataset & model type)</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox id="config.save_best_model" 
                                  checked={formData.config.save_best_model} 
                                  onCheckedChange={(checked) => handleInputChange('config.save_best_model', !!checked)} />
                        <Label htmlFor="config.save_best_model" className="text-sm font-normal">Save the best model found during search</Label>
                    </div>
                </CardContent>
              </Card>

              {/* Readonly Feature & Target from Dataset */}
              <Card>
                <CardHeader><CardTitle className="flex items-center"><ListChecks className="mr-2 h-5 w-5 text-primary"/>Dataset Features & Target</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                    <div>
                        <Label>Feature Columns (from dataset - read-only)</Label>
                        <ScrollArea className="h-20 mt-1 rounded-md border p-2 text-xs bg-muted/50">
                            {selectedDataset?.config.feature_columns.join(", ") || "N/A"}
                        </ScrollArea>
                    </div>
                    <div>
                        <Label>Target Column (from dataset - read-only)</Label>
                        <Input value={selectedDataset?.config.target_column || "N/A"} readOnly className="mt-1 bg-muted/50"/>
                    </div>
                </CardContent>
              </Card>
            </>
          )}

          {formError && (
            <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{formError}</AlertDescription></Alert>
          )}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !selectedDataset || isLoadingDatasets} size="lg">
              {isSubmitting ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting Job...</>
              ) : (
                <><Lightbulb className="mr-2 h-4 w-4" /> Start HP Search Job</>
              )}
            </Button>
          </div>
        </form>
      </PageContainer>
    </MainLayout>
  );
}

export default function CreateHpSearchJobPage() { // New wrapper component
  return (
    <Suspense fallback={<div>Loading page data...</div>}>
      <CreateHpSearchJobPageContent />
    </Suspense>
  );
}