"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter, useParams } // Import useParams
from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, GitBranch, RefreshCw, Database, BarChart3, Layers, Settings, Play, Eye, AlertCircle, Loader2, Puzzle, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";

import { apiService, handleApiError } from "@/lib/apiService";
import { Repository } from "@/types/api/repository"; 
import { DatasetRead } from "@/types/api/dataset"; 
import { MLModelRead } from "@/types/api/ml_model"; 
import { TrainingJobRead } from "@/types/api/training_job"; 
import { HPSearchJobRead } from "@/types/api/hp_search_job"; 
import { InferenceJobRead } from "@/types/api/inference_job"; 
import { BotPatternRead } from "@/types/api/bot_pattern"; 

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils"; // Your utility function

// Helper to create TypeScript types from Pydantic schemas (example for DatasetRead)
// You would do this for all relevant schemas in separate files (e.g., frontend/types/api/dataset.ts)
// For brevity, I'm assuming these types exist.

export default function RepositoryDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>(); // Get route params
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState("overview");
  const repoId = params.id;

  // Main repository data
  const [repository, setRepository] = useState<Repository | null>(null);
  const [isLoadingRepo, setIsLoadingRepo] = useState(true);
  const [repoError, setRepoError] = useState<string | null>(null);

  // Related data states
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [isLoadingTrainingJobs, setIsLoadingTrainingJobs] = useState(true);
  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [isLoadingHpSearchJobs, setIsLoadingHpSearchJobs] = useState(true);
  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [isLoadingInferenceJobs, setIsLoadingInferenceJobs] = useState(true);
  const [botPatterns, setBotPatterns] = useState<BotPatternRead[]>([]);
  const [isLoadingBotPatterns, setIsLoadingBotPatterns] = useState(true);
  
  const { taskStatuses } = useTaskStore();

  // Fetch main repository details
  useEffect(() => {
    if (!repoId) return;
    const fetchRepoData = async () => {
      setIsLoadingRepo(true);
      setRepoError(null);
      try {
        const repoData = await apiService.get<Repository>(`/repositories/${repoId}`);
        setRepository(repoData);
      } catch (err) {
        handleApiError(err, "Failed to fetch repository details");
        setRepoError(err instanceof Error ? err.message : "Repository not found or error loading.");
      } finally {
        setIsLoadingRepo(false);
      }
    };
    fetchRepoData();
  }, [repoId]);

  // Fetch related data once main repository is loaded
  useEffect(() => {
    if (!repository) return;

    const fetchAllRelatedData = async () => {
      setIsLoadingDatasets(true);
      setIsLoadingModels(true);
      setIsLoadingTrainingJobs(true);
      setIsLoadingHpSearchJobs(true);
      setIsLoadingInferenceJobs(true);
      setIsLoadingBotPatterns(true);

      const results = await Promise.allSettled([
        apiService.get<DatasetRead[]>(`/repositories/${repository.id}/datasets`),
        apiService.get<MLModelRead[]>(`/repositories/${repository.id}/models`),
        apiService.get<TrainingJobRead[]>(`/repositories/${repository.id}/training-jobs`),
        apiService.get<HPSearchJobRead[]>(`/repositories/${repository.id}/hp-search-jobs`),
        apiService.get<InferenceJobRead[]>(`/repositories/${repository.id}/inference-jobs`),
        apiService.get<BotPatternRead[]>(`/repositories/${repository.id}/bot-patterns?include_global=false`),
      ]);

      if (results[0].status === 'fulfilled') setDatasets(results[0].value); else handleApiError(results[0].reason, "Failed to fetch datasets");
      if (results[1].status === 'fulfilled') setModels(results[1].value); else handleApiError(results[1].reason, "Failed to fetch models");
      if (results[2].status === 'fulfilled') setTrainingJobs(results[2].value); else handleApiError(results[2].reason, "Failed to fetch training jobs");
      if (results[3].status === 'fulfilled') setHpSearchJobs(results[3].value); else handleApiError(results[3].reason, "Failed to fetch HP search jobs");
      if (results[4].status === 'fulfilled') setInferenceJobs(results[4].value); else handleApiError(results[4].reason, "Failed to fetch inference jobs");
      if (results[5].status === 'fulfilled') setBotPatterns(results[5].value); else handleApiError(results[5].reason, "Failed to fetch bot patterns");
      
      setIsLoadingDatasets(false);
      setIsLoadingModels(false);
      setIsLoadingTrainingJobs(false);
      setIsLoadingHpSearchJobs(false);
      setIsLoadingInferenceJobs(false);
      setIsLoadingBotPatterns(false);
    };

    fetchAllRelatedData();
  }, [repository]);


  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });
    } catch (e) { return "Invalid Date"; }
  };

  // Memoized status for the main repository ingestion
  const repoIngestionStatus = useMemo(() => {
    if (!repository) return undefined;
    return getLatestTaskForEntity(taskStatuses, "Repository", repository.id, "repository_ingestion");
  }, [taskStatuses, repository]);

  const getDisplayRepoStatus = () => {
    if (isLoadingRepo) return { text: "Loading...", badgeVariant: "outline" as const, icon: <Loader2 className="h-3 w-3 animate-spin" /> };
    if (repoError) return { text: "Error loading", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-3 w-3" /> };
    if (!repository) return { text: "Not found", badgeVariant: "destructive" as const };

    if (repoIngestionStatus) {
      if (repoIngestionStatus.status === "RUNNING" || repoIngestionStatus.status === "PENDING") {
        return { 
          text: `${repoIngestionStatus.status_message || repoIngestionStatus.status} (${repoIngestionStatus.progress ?? 0}%)`,
          badgeVariant: "outline"  as const, // Use shadcn outline for running
          icon: <RefreshCw className="h-3 w-3 animate-spin" />
        };
      }
      if (repoIngestionStatus.status === "SUCCESS") return { text: "Ingested", badgeVariant: "default" as const }; // Use shadcn default for success (usually green)
      if (repoIngestionStatus.status === "FAILED") return { text: "Ingestion Failed", badgeVariant: "destructive" as const };
    }
    // Fallback status based on repository data if no active/recent task
    return repository.datasets_count > 0 || repository.github_issues_count > 0 || repository.bot_patterns_count > 0 ? 
           { text: "Ingested (Idle)", badgeVariant: "default" as const } : 
           { text: "Ready to Ingest", badgeVariant: "secondary" as const };
  };
  
  const displayRepoStatusInfo = getDisplayRepoStatus();


  // Generic status badge renderer for jobs/datasets based on TaskStatusUpdatePayload
  const renderTaskAwareStatusBadge = (taskAwareEntityStatus?: TaskStatusUpdatePayload, fallbackText: string = "Unknown") => {
    if (!taskAwareEntityStatus) return <Badge variant="secondary">{fallbackText}</Badge>;

    const { status, status_message, progress } = taskAwareEntityStatus;
    switch (status) {
      case "SUCCESS":
        return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">Completed</Badge>;
      case "RUNNING":
      case "PENDING":
        return (
          <Badge variant="outline" className="border-blue-500 text-blue-700 dark:text-blue-400 flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            {status_message || status} ({progress ?? 0}%)
          </Badge>
        );
      case "FAILED":
        return <Badge variant="destructive" className="bg-red-100 text-red-700 dark:text-red-300">{status_message || "Failed"}</Badge>;
      default:
        return <Badge variant="secondary">{status_message || status || fallbackText}</Badge>;
    }
  };


  if (isLoadingRepo && !repository) {
    return (
      <MainLayout>
        <div className="container mx-auto py-6 space-y-6">
          <Skeleton className="h-10 w-3/4 mb-2" />
          <Skeleton className="h-6 w-1/2 mb-6" />
          <div className="grid grid-cols-3 gap-4 mb-6">
            <Skeleton className="h-24" /> <Skeleton className="h-24" /> <Skeleton className="h-24" />
          </div>
          <Skeleton className="h-10 w-full" /> {/* TabsList skeleton */}
          <Skeleton className="h-64 w-full mt-4" /> {/* Tab content skeleton */}
        </div>
      </MainLayout>
    );
  }

  if (repoError || !repository) {
    return (
      <MainLayout>
        <div className="container mx-auto py-6 text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-destructive mb-4" />
          <h1 className="text-2xl font-bold text-destructive mb-2">Error Loading Repository</h1>
          <p className="text-muted-foreground mb-6">{repoError || "The requested repository could not be found."}</p>
          <Button asChild variant="outline">
            <Link href="/repositories"><ArrowLeft className="mr-2 h-4 w-4" /> Back to Repositories</Link>
          </Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()} aria-label="Go back">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center">
              {repository.name} 
              <Badge variant={displayRepoStatusInfo.badgeVariant} className="ml-3 text-sm px-2 py-0.5">
                {displayRepoStatusInfo.icon && <span className="mr-1">{displayRepoStatusInfo.icon}</span>}
                {displayRepoStatusInfo.text}
              </Badge>
            </h1>
            <a href={repository.git_url} target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:underline truncate block max-w-md">
              {repository.git_url}
            </a>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-5">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="datasets">Datasets ({repository.datasets_count})</TabsTrigger>
            <TabsTrigger value="models">Models</TabsTrigger> {/* Count will come from fetched models.length */}
            <TabsTrigger value="jobs">Jobs</TabsTrigger> {/* Combined Jobs Tab */}
            <TabsTrigger value="bot-patterns">Bot Patterns ({repository.bot_patterns_count})</TabsTrigger>
          </TabsList>
          {/* OVERVIEW TAB */}
          <TabsContent value="overview" className="space-y-6"> {/* Increased spacing */}
            <Card>
              <CardHeader>
                <CardTitle>Repository Summary</CardTitle>
                <CardDescription>Key details and statistics for {repository.name}.</CardDescription>
              </CardHeader>
              <CardContent className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 text-sm"> {/* Increased gap */}
                <div>
                  <Label className="text-muted-foreground">Date Added</Label>
                  <p>{formatDate(repository.created_at)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Last Updated (Metadata)</Label>
                  <p>{formatDate(repository.updated_at)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Last Ingestion Activity</Label>
                  <p>{formatDate(repoIngestionStatus?.timestamp || null)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Datasets</Label>
                  <p className="font-semibold">{repository.datasets_count}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Bot Patterns (Specific)</Label>
                  <p className="font-semibold">{repository.bot_patterns_count}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Linked GitHub Issues</Label>
                  <p className="font-semibold">{repository.github_issues_count}</p>
                </div>
                {/* Placeholder for future stats */}
                <div>
                  <Label className="text-muted-foreground">Total Commits</Label>
                  <p>N/A</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Models Trained</Label>
                  <p>{isLoadingModels ? <Loader2 className="h-4 w-4 animate-spin" /> : models.length}</p>
                </div>
              </CardContent>
            </Card>
            
            <div className="grid gap-6 md:grid-cols-2"> {/* Increased gap */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-3"> {/* Adjusted padding */}
                        <CardTitle className="text-lg">Recent Datasets</CardTitle>
                        <Button variant="link" size="sm" onClick={() => setActiveTab("datasets")} className="text-primary">View All</Button>
                    </CardHeader>
                    <CardContent>
                        {isLoadingDatasets ? <Skeleton className="h-24 w-full"/> : datasets.length === 0 ? 
                            <p className="text-sm text-muted-foreground py-4 text-center">No datasets created yet.</p> :
                            <ul className="space-y-3"> {/* Increased spacing */}
                                {datasets.slice(0,3).map(ds => {
                                    const datasetTask = getLatestTaskForEntity(taskStatuses, "Dataset", ds.id, "dataset_generation");
                                    return (
                                    <li key={ds.id} className="text-sm flex justify-between items-center pb-2 border-b border-dashed last:border-b-0">
                                        <Link href={`/datasets/${ds.id}`} className="hover:underline font-medium truncate pr-2" title={ds.name}>{ds.name}</Link>
                                        {renderTaskAwareStatusBadge(datasetTask, ds.status)}
                                    </li>
                                )})}
                            </ul>
                        }
                         {datasets.length === 0 && !isLoadingDatasets && (
                            <Button className="w-full mt-4" size="sm" asChild>
                                <Link href={`/datasets/create?repository=${repoId}`}>
                                    <Plus className="mr-2 h-4 w-4" /> Create First Dataset
                                </Link>
                            </Button>
                        )}
                    </CardContent>
                </Card>
                 <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-3">
                        <CardTitle className="text-lg">Recent Jobs</CardTitle>
                         <Button variant="link" size="sm" onClick={() => setActiveTab("jobs")} className="text-primary">View All</Button>
                    </CardHeader>
                    <CardContent>
                        {(isLoadingTrainingJobs && isLoadingHpSearchJobs && isLoadingInferenceJobs) ? <Skeleton className="h-24 w-full"/> : 
                         (trainingJobs.length + hpSearchJobs.length + inferenceJobs.length === 0) ? <p className="text-sm text-muted-foreground py-4 text-center">No jobs run yet.</p> :
                            <ul className="space-y-3">
                                {trainingJobs.slice(0,1).map(job => {
                                    const jobTask = getLatestTaskForEntity(taskStatuses, "TrainingJob", job.id, "model_training");
                                    return (
                                    <li key={job.id} className="text-sm flex justify-between items-center pb-2 border-b border-dashed last:border-b-0">
                                       <Link href={`/jobs/${job.id}`} className="hover:underline font-medium truncate pr-2" title={`Train: ${job.config.model_name}`}>Train: {job.config.model_name}</Link>
                                       {renderTaskAwareStatusBadge(jobTask, job.status)}
                                    </li>
                                )})}
                                {hpSearchJobs.slice(0,1).map(job => {
                                     const jobTask = getLatestTaskForEntity(taskStatuses, "HPSearchJob", job.id, "hp_search");
                                     return (
                                     <li key={job.id} className="text-sm flex justify-between items-center pb-2 border-b border-dashed last:border-b-0">
                                        <Link href={`/jobs/${job.id}`} className="hover:underline font-medium truncate pr-2" title={`HP Search: ${job.optuna_study_name}`}>HP Search: {job.optuna_study_name}</Link>
                                        {renderTaskAwareStatusBadge(jobTask, job.status)}
                                     </li>
                                )})}
                                {inferenceJobs.slice(0,1).map(job => {
                                     const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id); // job_type could be feature_extraction or model_inference
                                     return (
                                     <li key={job.id} className="text-sm flex justify-between items-center pb-2 border-b border-dashed last:border-b-0">
                                        <Link href={`/prediction-insights/${job.id}`} className="hover:underline font-medium truncate pr-2" title={`Inference: ${formatDate(job.created_at)}`}>Inference: {formatDate(job.created_at)}</Link>
                                        {renderTaskAwareStatusBadge(jobTask, job.status)}
                                     </li>
                                )})}
                            </ul>
                        }
                         {(trainingJobs.length + hpSearchJobs.length + inferenceJobs.length === 0) && !(isLoadingTrainingJobs || isLoadingHpSearchJobs || isLoadingInferenceJobs) && (
                            <Button className="w-full mt-4" size="sm" asChild>
                                <Link href={`/jobs?repositoryId=${repoId}`}> {/* General link to jobs page, pre-filtered */}
                                    <Play className="mr-2 h-4 w-4" /> Start a Job
                                </Link>
                            </Button>
                        )}
                    </CardContent>
                </Card>
            </div>
          </TabsContent>

          {/* DATASETS TAB */}
          <TabsContent value="datasets" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Datasets for {repository.name}</h2>
              <Button asChild>
                <Link href={`/datasets/create?repository=${repoId}`}> {/* Use repoId from params */}
                  <Plus className="mr-2 h-4 w-4" /> Create Dataset
                </Link>
              </Button>
            </div>
            {isLoadingDatasets ? (
              <div className="rounded-md border p-4">
                <Skeleton className="h-8 w-full mb-2" />
                <Skeleton className="h-8 w-full mb-2" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : datasets.length === 0 ? (
              <Card>
                <CardContent className="pt-6 text-center text-muted-foreground">
                  <Database className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                  No datasets have been created for this repository yet.
                  <Button className="mt-4" asChild>
                     <Link href={`/datasets/create?repository=${repoId}`}>
                        <Plus className="mr-2 h-4 w-4" /> Create Your First Dataset
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="max-w-xs">Description</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {datasets.map((dataset) => {
                      const datasetTask = getLatestTaskForEntity(taskStatuses, "Dataset", dataset.id, "dataset_generation");
                      return (
                        <TableRow key={dataset.id}>
                          <TableCell className="font-medium break-all">{dataset.name}</TableCell>
                          <TableCell>{renderTaskAwareStatusBadge(datasetTask, dataset.status)}</TableCell>
                          <TableCell>{formatDate(dataset.created_at)}</TableCell>
                          <TableCell className="max-w-xs truncate" title={dataset.description || ""}>{dataset.description || "N/A"}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="outline" size="sm" asChild>
                              {/* This link should go to a new page: /datasets/[datasetId]/detail or similar */}
                              <Link href={`/datasets/${dataset.id}/detail`}>View Details</Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>

          {/* MODELS TAB */}
          {/* MODELS TAB */}
          <TabsContent value="models" className="space-y-4">
             <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">ML Models for {repository.name}</h2>
                <Button asChild>
                  {/* Link to a page to start training, pre-selecting this repo */}
                  <Link href={`/jobs/train?repositoryId=${repoId}`}> 
                    <Puzzle className="mr-2 h-4 w-4" /> Train New Model
                  </Link>
                </Button>
            </div>
            {isLoadingModels ? (
                 <div className="rounded-md border p-4"><Skeleton className="h-32 w-full"/></div>
            ) : models.length === 0 ? (
              <Card><CardContent className="pt-6 text-center text-muted-foreground">
                <BarChart3 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                No ML models have been trained for this repository yet.
                 <Button className="mt-4" asChild>
                     <Link href={`/jobs/train?repositoryId=${repoId}`}>
                        <Puzzle className="mr-2 h-4 w-4" /> Train Your First Model
                    </Link>
                  </Button>
              </CardContent></Card>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Version</TableHead><TableHead>Type</TableHead><TableHead>Dataset ID</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {models.map((model) => (
                      <TableRow key={model.id}>
                        <TableCell className="font-medium break-all">{model.name}</TableCell>
                        <TableCell>{model.version}</TableCell>
                        <TableCell><Badge variant="outline">{model.model_type}</Badge></TableCell>
                        <TableCell>
                            {model.dataset_id ? 
                                <Link href={`/datasets/${model.dataset_id}/detail`} className="hover:underline">{model.dataset_id}</Link> 
                                : "N/A"
                            }
                        </TableCell>
                        <TableCell>{formatDate(model.created_at)}</TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button variant="outline" size="sm" asChild>
                            {/* Link to a new page: /models/[modelId]/detail */}
                            <Link href={`/models/${model.id}/detail`}>View Model</Link>
                          </Button>
                          <Button variant="secondary" size="sm" asChild>
                            <Link href={`/jobs/inference?modelId=${model.id}&repositoryId=${repoId}`}>Run Inference</Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>

          <TabsContent value="jobs" className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">ML Jobs for {repository.name}</h2>
                <div className="space-x-2">
                    <Button variant="outline" size="sm" asChild><Link href={`/jobs/train?repositoryId=${repoId}`}>New Training</Link></Button>
                    <Button variant="outline" size="sm" asChild><Link href={`/jobs/hp-search?repositoryId=${repoId}`}>New HP Search</Link></Button>
                    {/* Inference is usually triggered from a model or commit, so less direct "New Inference Job" button here */}
                </div>
            </div>
            
            {/* Training Jobs Section */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-medium">Training Jobs</CardTitle>
                <CardDescription>Models trained using datasets from this repository.</CardDescription>
              </CardHeader>
              <CardContent>
              {isLoadingTrainingJobs ? <Skeleton className="h-24 w-full"/> : trainingJobs.length === 0 ? <p className="text-sm text-muted-foreground">No training jobs found.</p> : (
                <Table>
                  <TableHeader><TableRow><TableHead>Model Name</TableHead><TableHead>Dataset ID</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {trainingJobs.map(job => {
                        const jobTask = getLatestTaskForEntity(taskStatuses, "TrainingJob", job.id, "model_training");
                        return(
                        <TableRow key={job.id}>
                            <TableCell className="font-medium break-all">{job.config.model_name}</TableCell>
                            <TableCell><Link href={`/datasets/${job.dataset_id}/detail`} className="hover:underline">{job.dataset_id}</Link></TableCell>
                            <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                            <TableCell>{formatDate(job.created_at)}</TableCell>
                            <TableCell className="text-right">
                                <Button variant="outline" size="sm" asChild><Link href={`/jobs/${job.id}/detail`}>Details</Link></Button> {/* Link to specific job detail page */}
                                {job.ml_model_id && job.status === "success" &&
                                    <Button variant="link" size="sm" asChild className="ml-2"><Link href={`/models/${job.ml_model_id}/detail`}>View Model</Link></Button>
                                }
                            </TableCell>
                        </TableRow>
                    )})}
                  </TableBody>
                </Table>
              )}
              </CardContent>
            </Card>

            {/* HP Search Jobs Section */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-medium">Hyperparameter Search Jobs</CardTitle>
                 <CardDescription>Optuna studies run for this repository's datasets.</CardDescription>
              </CardHeader>
              <CardContent>
              {isLoadingHpSearchJobs ? <Skeleton className="h-24 w-full"/> : hpSearchJobs.length === 0 ? <p className="text-sm text-muted-foreground">No HP search jobs found.</p> : (
                 <Table>
                  <TableHeader><TableRow><TableHead>Study Name</TableHead><TableHead>Dataset ID</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {hpSearchJobs.map(job => {
                        const jobTask = getLatestTaskForEntity(taskStatuses, "HPSearchJob", job.id, "hp_search");
                        return(
                        <TableRow key={job.id}>
                            <TableCell className="font-medium break-all">{job.optuna_study_name}</TableCell>
                            <TableCell><Link href={`/datasets/${job.dataset_id}/detail`} className="hover:underline">{job.dataset_id}</Link></TableCell>
                            <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                            <TableCell>{formatDate(job.created_at)}</TableCell>
                            <TableCell className="text-right"><Button variant="outline" size="sm" asChild><Link href={`/jobs/${job.id}/detail`}>Details</Link></Button></TableCell>
                        </TableRow>
                    )})}
                  </TableBody>
                </Table>
              )}
              </CardContent>
            </Card>

             {/* Inference Jobs Section */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-medium">Inference Jobs</CardTitle>
                <CardDescription>Predictions made using models trained on this repository's data.</CardDescription>
              </CardHeader>
              <CardContent>
              {isLoadingInferenceJobs ? <Skeleton className="h-24 w-full"/> : inferenceJobs.length === 0 ? <p className="text-sm text-muted-foreground">No inference jobs found.</p> : (
                 <Table>
                  <TableHeader><TableRow><TableHead>Input Reference</TableHead><TableHead>Model ID</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {inferenceJobs.map(job => {
                        // Inference can have multiple task stages (feature extraction, then prediction)
                        // We might need a more sophisticated way to get combined status or link to the final prediction task.
                        // For now, using 'model_inference' as a placeholder job_type for its Celery task from ML worker.
                        const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id, "model_inference"); 
                        return(
                        <TableRow key={job.id}>
                            <TableCell className="font-mono text-xs max-w-[200px] truncate" title={typeof job.input_reference === 'object' ? JSON.stringify(job.input_reference) : String(job.input_reference)}>
                                {typeof job.input_reference === 'object' ? 
                                  (job.input_reference.commit_hash ? `Commit: ${String(job.input_reference.commit_hash).substring(0,8)}...` : JSON.stringify(job.input_reference)) 
                                  : String(job.input_reference)
                                }
                            </TableCell>
                             <TableCell><Link href={`/models/${job.ml_model_id}/detail`} className="hover:underline">{job.ml_model_id}</Link></TableCell>
                            <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                            <TableCell>{formatDate(job.created_at)}</TableCell>
                            <TableCell className="text-right"><Button variant="outline" size="sm" asChild><Link href={`/prediction-insights/${job.id}`}>View Insights</Link></Button></TableCell>
                        </TableRow>
                    )})}
                  </TableBody>
                </Table>
              )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* BOT PATTERNS TAB */}
          <TabsContent value="bot-patterns" className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Repository-Specific Bot Patterns</h2>
                <Button asChild>
                  <Link href={`/bot-patterns?repository=${repoId}`}> {/* Use repoId */}
                    <Settings className="mr-2 h-4 w-4" /> Manage Patterns
                  </Link>
                </Button>
            </div>
            {isLoadingBotPatterns ? (
                <div className="rounded-md border p-4"><Skeleton className="h-32 w-full"/></div>
            ) : botPatterns.length === 0 ? (
              <Card><CardContent className="pt-6 text-center text-muted-foreground">
                 <Layers className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                No repository-specific bot patterns defined. 
                <Link href="/bot-patterns" className="text-primary hover:underline ml-1">Global patterns</Link> will apply.
                <Button className="mt-4 w-full" asChild>
                     <Link href={`/bot-patterns?repository=${repoId}`}>
                        <Plus className="mr-2 h-4 w-4" /> Add Repository-Specific Pattern
                    </Link>
                  </Button>
                </CardContent></Card>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader><TableRow><TableHead>Pattern</TableHead><TableHead>Type</TableHead><TableHead>Exclusion</TableHead><TableHead>Description</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {botPatterns.map((pattern) => (
                      <TableRow key={pattern.id}>
                        <TableCell className="font-mono break-all">{pattern.pattern}</TableCell>
                        <TableCell><Badge variant="secondary">{pattern.pattern_type}</Badge></TableCell>
                        <TableCell>{pattern.is_exclusion ? "Yes" : "No"}</TableCell>
                        <TableCell className="max-w-md truncate" title={pattern.description || ""}>{pattern.description || "N/A"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}