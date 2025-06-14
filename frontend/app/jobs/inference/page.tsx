// frontend/app/jobs/inference/page.tsx
"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { SearchableSelect, SearchableSelectOption } from "@/components/ui/searchable-select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Play,
  Wand2,
  GitBranch,
  BarChart3,
  Loader2,
  AlertCircle,
  CheckCircle,
  Eye,
  RefreshCw,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { Repository, PaginatedRepositoryRead } from "@/types/api/repository";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import {
  InferenceJobRead,
  PaginatedInferenceJobRead,
  ManualInferenceRequestPayload,
  InferenceTriggerResponse,
} from "@/types/api/inference-job";
import { useTaskStore } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";

export default function ManualInferencePage() {
  const router = useRouter();
  const { toast } = useToast();
  const searchParams = useSearchParams();

  const [selectedRepoId, setSelectedRepoId] = useState<string>("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const [commitHash, setCommitHash] = useState<string>("");

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const [recentInferenceJobs, setRecentInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [isLoadingRecentJobs, setIsLoadingRecentJobs] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { taskStatuses } = useTaskStore();

  const fetchRepositories = useCallback(async () => {
    setIsLoadingRepositories(true);
    try {
      const data = await apiService.getRepositories({ limit: 200 });
      setRepositories(data.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch repositories");
    } finally {
      setIsLoadingRepositories(false);
    }
  }, []);

  const fetchModelsForRepo = useCallback(async (repoId: string) => {
    setIsLoadingModels(true);
    setModels([]); // Clear previous models
    setSelectedModelId(""); // Reset model selection
    if (!repoId) {
      setIsLoadingModels(false);
      return;
    }
    try {
      const paginatedModels = await apiService.get<PaginatedMLModelRead>(
        `/repositories/${repoId}/models?limit=200`
      );
      setModels(paginatedModels.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch models for repository");
    } finally {
      setIsLoadingModels(false);
    }
  }, []);

  const fetchRecentInferenceJobs = useCallback(async () => {
    setIsLoadingRecentJobs(true);
    try {
      const response = await apiService.getInferenceJobs({ limit: 10 });
      setRecentInferenceJobs(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch recent inference jobs");
    } finally {
      setIsLoadingRecentJobs(false);
    }
  }, []);

  useEffect(() => {
    fetchRepositories();
    fetchRecentInferenceJobs();

    const queryRepoId = searchParams.get("repositoryId");
    const queryCommitHash = searchParams.get("commitHash");

    if (queryRepoId) {
      setSelectedRepoId(queryRepoId);
    }
    if (queryCommitHash) {
      setCommitHash(queryCommitHash);
    }
  }, [fetchRepositories, fetchRecentInferenceJobs, searchParams]);

  useEffect(() => {
    if (selectedRepoId) {
      fetchModelsForRepo(selectedRepoId);
    } else {
      setModels([]);
    }
  }, [selectedRepoId, fetchModelsForRepo]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedRepoId) {
      setFormError("Please select a repository.");
      return;
    }
    if (!selectedModelId) {
      setFormError("Please select a model.");
      return;
    }
    if (!commitHash.trim()) {
      setFormError("Please enter a commit hash.");
      return;
    }
    if (commitHash.trim().length < 7) {
      setFormError("Commit hash must be at least 7 characters long.");
      return;
    }

    setIsSubmitting(true);
    const payload: ManualInferenceRequestPayload = {
      repo_id: parseInt(selectedRepoId), // Ensure selectedRepoId is parsed to int
      ml_model_id: parseInt(selectedModelId), // Ensure selectedModelId is parsed to int
      target_commit_hash: commitHash.trim(),
    };

    try {
      const response = await apiService.post<
        InferenceTriggerResponse,
        ManualInferenceRequestPayload
      >("/ml/infer/manual", payload);
      toast({
        title: "Inference Triggered",
        description: `Job ${response.inference_job_id} is processing. Task: ${response.initial_task_id}`,
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/prediction-insights/${response.inference_job_id}`}>View Progress</Link>
          </Button>
        ),
      });
      setCommitHash("");
      setTimeout(() => fetchRecentInferenceJobs(), 1000); // Refresh list after a short delay
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
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderTaskAwareStatusBadge = (job: InferenceJobRead) => {
    const liveTaskStatus = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id);
    const displayStatus = liveTaskStatus?.status || job.status;
    const displayMessage = liveTaskStatus?.status_message || job.status_message;
    const progress = liveTaskStatus?.progress;

    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = String(displayStatus).toUpperCase();

    switch (
      displayStatus
        .toUpperCase()
        .replace("JOBSTATUSENUM", "")
        .replace("TASKSTATUSENUM", "")
        .replace(".", "")
    ) {
      case JobStatusEnum.SUCCESS.toUpperCase():
        badgeVariant = "default";
        icon = <CheckCircle className="h-3 w-3 mr-1" />;
        text = "Success";
        break;
      case JobStatusEnum.RUNNING.toUpperCase():
      case JobStatusEnum.STARTED.toUpperCase():
      case "GENERATING": // From dataset generation tasks
      case "EXTRACTING_FEATURES": // Custom status from task
        badgeVariant = "outline";
        icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />;
        text = `${displayMessage || displayStatus} (${progress ?? 0}%)`;
        break;
      case JobStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline";
        icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />;
        text = "Pending";
        break;
      case JobStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive";
        icon = <AlertCircle className="h-3 w-3 mr-1" />;
        text = "Failed";
        break;
      case JobStatusEnum.REVOKED.toUpperCase():
        badgeVariant = "destructive";
        icon = <AlertCircle className="h-3 w-3 mr-1" />;
        text = "Revoked";
        break;
    }
    return (
      <Badge
        variant={badgeVariant}
        className="whitespace-nowrap text-xs px-1.5 py-0.5"
        title={displayMessage || String(displayStatus)}
      >
        {icon}
        {text}
      </Badge>
    );
  };

  const repositoryOptions: SearchableSelectOption[] = useMemo(
    () => repositories.map((repo) => ({ value: repo.id.toString(), label: repo.name })),
    [repositories]
  );

  const modelOptions: SearchableSelectOption[] = useMemo(
    () =>
      models.map((model) => ({
        value: model.id.toString(),
        label: `${model.name} (v${model.version})`,
      })),
    [models]
  );

  return (
    <MainLayout>
      <PageContainer
        title="Manual Inference"
        description="Run a trained model against a specific commit for defect prediction."
        actions={
          <Button variant="outline" onClick={() => router.push("/jobs")}>
            <ArrowLeft className="mr-2 h-4 w-4" /> All Jobs
          </Button>
        }
      >
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="md:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Wand2 className="mr-2 h-5 w-5 text-primary" />
                Configure Inference
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="repository_id">Repository *</Label>
                  {isLoadingRepositories ? (
                    <Skeleton className="h-10 w-full" />
                  ) : (
                    <SearchableSelect
                      value={selectedRepoId}
                      onValueChange={setSelectedRepoId}
                      options={repositoryOptions}
                      placeholder="Select a repository..."
                      searchPlaceholder="Search repositories..."
                      emptyMessage="No repositories found."
                      disabled={isLoadingRepositories}
                    />
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="ml_model_id">Model *</Label>
                  {isLoadingModels ? (
                    <Skeleton className="h-10 w-full" />
                  ) : (
                    <SearchableSelect
                      value={selectedModelId}
                      onValueChange={setSelectedModelId}
                      options={modelOptions}
                      placeholder={
                        !selectedRepoId
                          ? "Select repository first"
                          : models.length === 0
                            ? "No models for this repo"
                            : "Select a model..."
                      }
                      searchPlaceholder="Search models..."
                      emptyMessage="No models found."
                      disabled={isLoadingModels || !selectedRepoId || models.length === 0}
                    />
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="target_commit_hash">Commit Hash *</Label>
                  <Input
                    id="target_commit_hash"
                    value={commitHash}
                    onChange={(e) => setCommitHash(e.target.value)}
                    placeholder="Enter full or short commit SHA"
                    required
                  />
                </div>

                {formError && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{formError}</AlertDescription>
                  </Alert>
                )}

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting || !selectedRepoId || !selectedModelId || !commitHash}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Triggering...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" /> Trigger Inference
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center">
                <BarChart3 className="mr-2 h-5 w-5 text-primary" />
                Recent Inference Jobs
              </CardTitle>
              <CardDescription>
                Latest inference jobs submitted across all repositories.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Commit</TableHead>
                      <TableHead>Model Used</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isLoadingRecentJobs ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <TableRow key={i}>
                          <TableCell colSpan={5}>
                            <Skeleton className="h-8 w-full" />
                          </TableCell>
                        </TableRow>
                      ))
                    ) : recentInferenceJobs.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                          No recent jobs to display.
                        </TableCell>
                      </TableRow>
                    ) : (
                      recentInferenceJobs.map((job) => {
                        const repo = repositories.find((r) => r.id === job.input_reference.repo_id);
                        const model =
                          models.find((m) => m.id === job.ml_model_id) ||
                          (selectedRepoId === job.input_reference.repo_id.toString()
                            ? models.find((m) => m.id === job.ml_model_id)
                            : null); // Attempt to find model in current list if repo matches
                        return (
                          <TableRow key={job.id}>
                            <TableCell className="font-mono text-xs">
                              <Link
                                href={`/repositories/${job.input_reference.repo_id}/commits/${job.input_reference.commit_hash}`}
                                className="hover:underline text-primary"
                              >
                                {String(job.input_reference.commit_hash).substring(0, 8)}...
                              </Link>
                              <span className="block text-muted-foreground">
                                {repo?.name || `Repo ${job.input_reference.repo_id}`}
                              </span>
                            </TableCell>
                            <TableCell
                              className="text-xs truncate max-w-[150px]"
                              title={
                                model ? `${model.name} v${model.version}` : `ID: ${job.ml_model_id}`
                              }
                            >
                              {model ? (
                                <Link
                                  href={`/models/${job.ml_model_id}`}
                                  className="hover:underline"
                                >{`${model.name.substring(0, 20)}... v${model.version}`}</Link>
                              ) : (
                                `Model ID: ${job.ml_model_id}`
                              )}
                            </TableCell>
                            <TableCell>{renderTaskAwareStatusBadge(job)}</TableCell>
                            <TableCell className="text-xs">{formatDate(job.created_at)}</TableCell>
                            <TableCell className="text-right">
                              {job.status === JobStatusEnum.SUCCESS ? (
                                <Button variant="outline" size="sm" asChild>
                                  <Link href={`/prediction-insights/${job.id}`}>
                                    <Eye className="mr-1 h-3 w-3" />
                                    Insights
                                  </Link>
                                </Button>
                              ) : (
                                <Button variant="outline" size="sm" disabled>
                                  <Eye className="mr-1 h-3 w-3" />
                                  Insights
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </PageContainer>
    </MainLayout>
  );
}
