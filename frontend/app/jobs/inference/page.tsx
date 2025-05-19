// frontend/app/jobs/inference/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectGroup, SelectLabel
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Play, Wand2, GitBranch, BarChart3, Loader2, AlertCircle, CheckCircle, Eye, RefreshCw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { Repository } from "@/types/api/repository";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import { InferenceJobRead, PaginatedInferenceJobRead, ManualInferenceRequestPayload, InferenceTriggerResponse } from "@/types/api/inference-job";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";

const API_ENDPOINT_REPOSITORIES = "/repositories";
const API_ENDPOINT_MODELS = "/ml/models";
const API_ENDPOINT_TRIGGER_INFERENCE = "/ml/infer/manual";
const API_ENDPOINT_LIST_INFERENCE_JOBS = "/ml/infer";

const ITEMS_PER_PAGE = 5;

export default function ManualInferencePage() {
  const router = useRouter();
  const { toast } = useToast();

  const [selectedRepoId, setSelectedRepoId] = useState<string>("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const [commitHash, setCommitHash] = useState<string>("");

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false); // Initially false, load on repo select

  const [recentInferenceJobs, setRecentInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [isLoadingRecentJobs, setIsLoadingRecentJobs] = useState(false);
  // No pagination for recent jobs list for now, keep it simple

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  
  const { taskStatuses } = useTaskStore();

  const fetchRepositories = useCallback(async () => {
    setIsLoadingRepositories(true);
    try {
      const data = await apiService.get<Repository[]>(API_ENDPOINT_REPOSITORIES);
      setRepositories(data || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch repositories");
    } finally {
      setIsLoadingRepositories(false);
    }
  }, []);

  const fetchModels = useCallback(async (repoId?: string) => {
    setIsLoadingModels(true);
    setModels([]); // Clear previous models
    try {
      let endpoint = API_ENDPOINT_MODELS;
      // If repoId is provided, eventually filter models by those compatible with the repo
      // For now, we fetch all models or models related to a repo if API supports `repository_id` filter for models
      if (repoId) {
          // Assuming /repositories/{repoId}/models endpoint exists or /ml/models?repository_id=...
          // Let's use the existing /repositories/{repoId}/models
          const paginatedModels = await apiService.get<PaginatedMLModelRead>(`/repositories/${repoId}/models?limit=100`);
          setModels(paginatedModels.items || []);
      } else {
          const paginatedModels = await apiService.get<PaginatedMLModelRead>(`${API_ENDPOINT_MODELS}?limit=100`);
          setModels(paginatedModels.items || []);
      }

    } catch (err) {
      handleApiError(err, "Failed to fetch models");
    } finally {
      setIsLoadingModels(false);
    }
  }, []);
  
  const fetchRecentInferenceJobs = useCallback(async (repoId?: string, modelId?: string) => {
    setIsLoadingRecentJobs(true);
    try {
        const params = new URLSearchParams({ limit: String(ITEMS_PER_PAGE) });
        // Ideally, filter by repoId if possible backend-side or filter from a larger list client-side
        // For now, let's just filter by model_id if present, and show all recent if no model/repo
        if (modelId) params.append("model_id", modelId);
        // If repoId is available, and your backend /ml/infer endpoint can filter by repo (indirectly via model's dataset), that's better.
        // For now, we might just show latest overall if no repo/model specific filtering is easy.
        
        const response = await apiService.get<PaginatedInferenceJobRead>(`${API_ENDPOINT_LIST_INFERENCE_JOBS}?${params.toString()}`);
        setRecentInferenceJobs(response.items || []);
    } catch (err) {
        handleApiError(err, "Failed to fetch recent inference jobs");
    } finally {
        setIsLoadingRecentJobs(false);
    }
  }, []);


  useEffect(() => {
    fetchRepositories();
    fetchRecentInferenceJobs(); // Fetch general recent jobs on initial load
  }, [fetchRepositories, fetchRecentInferenceJobs]);

  useEffect(() => {
    if (selectedRepoId) {
      fetchModels(selectedRepoId); // Fetch models when a repository is selected
      // Optionally, fetch recent jobs specific to this repo if API supports
      // fetchRecentInferenceJobs(selectedRepoId); 
    } else {
      setModels([]); // Clear models if no repo is selected
    }
  }, [selectedRepoId, fetchModels]);
  
  useEffect(() => {
    // Fetch recent jobs when repo or model selection changes to refine the list
    fetchRecentInferenceJobs(selectedRepoId, selectedModelId);
  }, [selectedRepoId, selectedModelId, fetchRecentInferenceJobs]);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedRepoId) {
      setFormError("Please select a repository."); return;
    }
    if (!selectedModelId) {
      setFormError("Please select a model."); return;
    }
    if (!commitHash.trim()) {
      setFormError("Please enter a commit hash."); return;
    }
    if (commitHash.trim().length < 7) {
      setFormError("Commit hash must be at least 7 characters long."); return;
    }


    setIsSubmitting(true);
    const payload: ManualInferenceRequestPayload = {
      repo_id: parseInt(selectedRepoId),
      ml_model_id: parseInt(selectedModelId),
      target_commit_hash: commitHash.trim(),
    };

    try {
      const response = await apiService.post<InferenceTriggerResponse, ManualInferenceRequestPayload>(
        API_ENDPOINT_TRIGGER_INFERENCE,
        payload
      );
      toast({
        title: "Inference Triggered",
        description: `Inference job ${response.inference_job_id} (Task: ${response.initial_task_id}) submitted.`,
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/prediction-insights/${response.inference_job_id}`}>View Insights</Link>
          </Button>
        ),
      });
      setCommitHash(""); // Clear commit hash input
      fetchRecentInferenceJobs(selectedRepoId, selectedModelId); // Refresh recent jobs
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        handleApiError(err, "Failed to trigger inference");
        setFormError("An unexpected error occurred.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDate = (dateString?: string | Date | null): string => {
    if (!dateString) return "N/A";
    const date = typeof dateString === "string" ? new Date(dateString) : dateString;
    return date.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  };

  const renderTaskAwareStatusBadge = (taskAwareEntityStatus?: TaskStatusUpdatePayload, fallbackStaticStatus?: string) => {
    const currentStatusToDisplay = taskAwareEntityStatus || (fallbackStaticStatus ? { status: fallbackStaticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusToDisplay || !currentStatusToDisplay.status) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusToDisplay;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (String(status).toUpperCase()) {
      case JobStatusEnum.SUCCESS.toUpperCase(): badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = "Success"; break;
      case JobStatusEnum.RUNNING.toUpperCase(): case JobStatusEnum.STARTED.toUpperCase():
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `Running (${progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; text = "Pending"; break;
      case JobStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = `Failed${status_message ? ': '+status_message.substring(0,30)+'...' : ''}`; break;
      case JobStatusEnum.REVOKED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = "Revoked"; break;
      default: text = String(status).toUpperCase();
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap text-xs px-1.5 py-0.5" title={status_message || status || ''}>{icon}{text}</Badge>;
  };


  return (
    <MainLayout>
      <PageContainer
        title="Manual Inference Trigger"
        description="Run a trained model against a specific commit for defect prediction."
        actions={
          <Button variant="outline" onClick={() => router.push('/jobs')}>
            <ArrowLeft className="mr-2 h-4 w-4" /> All Jobs
          </Button>
        }
      >
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="md:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center"><Wand2 className="mr-2 h-5 w-5 text-primary"/>Configure Inference</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="repository_id">Repository *</Label>
                  {isLoadingRepositories ? <Skeleton className="h-10 w-full" /> : (
                    <Select value={selectedRepoId} onValueChange={(value) => {setSelectedRepoId(value); setSelectedModelId(""); /* Reset model */}}>
                      <SelectTrigger id="repository_id"><SelectValue placeholder="Select a repository..." /></SelectTrigger>
                      <SelectContent>
                        {repositories.map(repo => (<SelectItem key={repo.id} value={repo.id.toString()}>{repo.name}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="ml_model_id">Model *</Label>
                  {isLoadingModels ? <Skeleton className="h-10 w-full" /> : (
                    <Select value={selectedModelId} onValueChange={setSelectedModelId} disabled={!selectedRepoId || models.length === 0}>
                      <SelectTrigger id="ml_model_id"><SelectValue placeholder={!selectedRepoId ? "Select repository first" : (models.length === 0 ? "No models for this repo" : "Select a model...")} /></SelectTrigger>
                      <SelectContent>
                        {models.map(model => (<SelectItem key={model.id} value={model.id.toString()}>{model.name} (v{model.version}) - {model.model_type}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="target_commit_hash">Commit Hash *</Label>
                  <Input id="target_commit_hash" value={commitHash} onChange={(e) => setCommitHash(e.target.value)} placeholder="Enter full or short commit SHA" required />
                </div>
                
                {formError && (
                  <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{formError}</AlertDescription></Alert>
                )}

                <Button type="submit" className="w-full" disabled={isSubmitting || !selectedRepoId || !selectedModelId}>
                  {isSubmitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Triggering...</> : <><Play className="mr-2 h-4 w-4" /> Trigger Inference</>}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center"><BarChart3 className="mr-2 h-5 w-5 text-primary"/>Recent Inference Jobs</CardTitle>
              <CardDescription>
                Showing latest jobs. {selectedModelId ? `Filtered by model ${selectedModelId}.` : (selectedRepoId ? `Filtered by repository ${selectedRepoId}.`: "All repositories.")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingRecentJobs ? (
                <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full" />)}</div>
              ) : recentInferenceJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No recent inference jobs to display for the current selection.</p>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader><TableRow><TableHead>Commit</TableHead><TableHead>Model</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {recentInferenceJobs.map(job => {
                        const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id);
                        const commit = typeof job.input_reference === 'object' && job.input_reference.commit_hash ? String(job.input_reference.commit_hash).substring(0, 8) : "N/A";
                        const modelUsed = models.find(m => m.id === job.ml_model_id);
                        return (
                          <TableRow key={job.id}>
                            <TableCell className="font-mono text-xs" title={typeof job.input_reference === 'object' && job.input_reference.commit_hash ? String(job.input_reference.commit_hash): ""}>{commit}</TableCell>
                            <TableCell className="text-xs truncate max-w-[150px]" title={modelUsed ? `${modelUsed.name} v${modelUsed.version}`: `ID: ${job.ml_model_id}`}>
                                {modelUsed ? <Link href={`/models/${job.ml_model_id}`} className="hover:underline">{`${modelUsed.name.substring(0,20)}... v${modelUsed.version}`}</Link> : `ID: ${job.ml_model_id}`}
                            </TableCell>
                            <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                            <TableCell className="text-xs">{formatDate(job.created_at)}</TableCell>
                            <TableCell className="text-right">
                              {job.status === JobStatusEnum.SUCCESS ? (
                                <Button variant="outline" size="sm" asChild>
                                    <Link href={`/prediction-insights/${job.id}`}><Eye className="mr-1 h-3 w-3"/>Insights</Link>
                                </Button>
                              ) : (
                                 <Button variant="outline" size="sm" disabled><Eye className="mr-1 h-3 w-3"/>Insights</Button>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
             <CardFooter>
                <Button variant="link" size="sm" className="mx-auto" onClick={() => fetchRecentInferenceJobs(selectedRepoId, selectedModelId)} disabled={isLoadingRecentJobs}>
                    <RefreshCw className={`mr-2 h-3 w-3 ${isLoadingRecentJobs ? 'animate-spin' : ''}`}/>Refresh Recent Jobs
                </Button>
            </CardFooter>
          </Card>
        </div>
      </PageContainer>
    </MainLayout>
  );
}