"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react"; // Added React, useCallback
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, RefreshCw, Database, BarChart3, Layers, Settings, Play, Eye, AlertCircle, Loader2, Puzzle, Plus, CheckCircle, GitCommit } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";

import { apiService, handleApiError } from "@/lib/apiService";
import { Repository } from "@/types/api/repository";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import { TrainingJobRead, PaginatedTrainingJobRead } from "@/types/api/training-job";
import { HPSearchJobRead, PaginatedHPSearchJobRead } from "@/types/api/hp-search-job";
import { InferenceJobRead, PaginatedInferenceJobRead } from "@/types/api/inference-job";
import { BotPatternRead, PaginatedBotPatternRead } from "@/types/api/bot-pattern";

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";
import { RepositoryCommitsTab } from "@/components/repositories/RepositoryCommitsTab";
import { CommitListItem } from "@/types/api";

const ITEMS_PER_PAGE = 5; // Common limit for tab lists

export default function RepositoryDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState("overview");
  const repoId = params.id;

  const [repository, setRepository] = useState<Repository | null>(null);
  const [isLoadingRepo, setIsLoadingRepo] = useState(true);
  const [repoError, setRepoError] = useState<string | null>(null);

  const [recentCommits, setRecentCommits] = useState<CommitListItem[]>([]);
  const [isLoadingCommits, setIsLoadingCommits] = useState(true);
  const [selectedCommitDialog, setSelectedCommitDialog] = useState<string | null>(null);

  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [datasetsPagination, setDatasetsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [modelsPagination, setModelsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [trainingJobsPagination, setTrainingJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [hpSearchJobsPagination, setHpSearchJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [inferenceJobsPagination, setInferenceJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [botPatterns, setBotPatterns] = useState<BotPatternRead[]>([]);
  const [botPatternsPagination, setBotPatternsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  
  const { taskStatuses } = useTaskStore();

  const fetchMainRepositoryData = useCallback(async () => {
    if (!repoId) return;
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
  }, [repoId]);

  const fetchRecentCommits = useCallback(async () => {
    if(!repoId) return;
    setIsLoadingCommits(true);
    try {
        const response = await apiService.getCommits(repoId, { limit: 10 });
        setRecentCommits(response.items || []);
    } catch (err) {
        // Silently fail for tab content or show small inline error
    } finally {
        setIsLoadingCommits(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchMainRepositoryData();
    fetchRecentCommits();
  }, [fetchMainRepositoryData, fetchRecentCommits]);

  // --- Paginated Fetch Functions ---
  const fetchPaginatedDatasets = useCallback(async (page: number) => {
    if (!repoId || !repository) return;
    setDatasetsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
    try {
        const response = await apiService.get<PaginatedDatasetRead>(`/repositories/${repoId}/datasets?skip=${skip}&limit=${ITEMS_PER_PAGE}`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setDatasets(response.items);
            setDatasetsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
        } else {
            console.error("Unexpected response structure for datasets:", response);
            handleApiError({ message: "Received invalid data structure for datasets." }, "Failed to fetch datasets");
            setDatasets([]);
            setDatasetsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch datasets");
        setDatasetsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0 }));
        setDatasets([]);
    }
  }, [repoId, repository]);

  const fetchPaginatedModels = useCallback(async (page: number) => {
    if (!repoId || !repository) return;
    setModelsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
    try {
        const response = await apiService.get<PaginatedMLModelRead>(`/repositories/${repoId}/models?skip=${skip}&limit=${ITEMS_PER_PAGE}`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setModels(response.items);
            setModelsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
        } else {
            console.error("Unexpected response structure for models:", response);
            handleApiError({ message: "Received invalid data structure for models." }, "Failed to fetch models");
            setModels([]);
            setModelsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch models");
        setModelsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0 }));
        setModels([]);
    }
  }, [repoId, repository]);

  const fetchPaginatedTrainingJobs = useCallback(async (page: number) => {
    if(!repoId || !repository) return;
    setTrainingJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
    try {
        const response = await apiService.get<PaginatedTrainingJobRead>(`/repositories/${repoId}/training-jobs?skip=${skip}&limit=${ITEMS_PER_PAGE}`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setTrainingJobs(response.items);
            setTrainingJobsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false}));
        } else {
            console.error("Unexpected response structure for training jobs:", response);
            handleApiError({ message: "Received invalid data structure for training jobs." }, "Failed to fetch training jobs");
            setTrainingJobs([]);
            setTrainingJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false}));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch training jobs");
        setTrainingJobsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0}));
        setTrainingJobs([]);
    }
  }, [repoId, repository]);

  const fetchPaginatedHpSearchJobs = useCallback(async (page: number) => {
    if(!repoId || !repository) return;
    setHpSearchJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
     try {
        const response = await apiService.get<PaginatedHPSearchJobRead>(`/repositories/${repoId}/hp-search-jobs?skip=${skip}&limit=${ITEMS_PER_PAGE}`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setHpSearchJobs(response.items);
            setHpSearchJobsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false}));
        } else {
            console.error("Unexpected response structure for HP search jobs:", response);
            handleApiError({ message: "Received invalid data structure for HP search jobs." }, "Failed to fetch HP search jobs");
            setHpSearchJobs([]);
            setHpSearchJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false}));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch HP search jobs");
        setHpSearchJobsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0}));
        setHpSearchJobs([]);
    }
  }, [repoId, repository]);

  const fetchPaginatedInferenceJobs = useCallback(async (page: number) => {
    if(!repoId || !repository) return;
    setInferenceJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
     try {
        const response = await apiService.get<PaginatedInferenceJobRead>(`/repositories/${repoId}/inference-jobs?skip=${skip}&limit=${ITEMS_PER_PAGE}`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setInferenceJobs(response.items);
            setInferenceJobsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false}));
        } else {
            console.error("Unexpected response structure for inference jobs:", response);
            handleApiError({ message: "Received invalid data structure for inference jobs." }, "Failed to fetch inference jobs");
            setInferenceJobs([]);
            setInferenceJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false}));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch inference jobs");
        setInferenceJobsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0}));
        setInferenceJobs([]);
    }
  }, [repoId, repository]);

  const fetchPaginatedBotPatterns = useCallback(async (page: number) => {
    if(!repoId || !repository) return;
    setBotPatternsPagination(prev => ({ ...prev, isLoading: true, currentPage: page, totalItems: page === 1 ? 0 : prev.totalItems }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
     try {
        const response = await apiService.get<PaginatedBotPatternRead>(`/repositories/${repoId}/bot-patterns?skip=${skip}&limit=${ITEMS_PER_PAGE}&include_global=false`);
        if (response && Array.isArray(response.items) && typeof response.total === 'number') {
            setBotPatterns(response.items);
            setBotPatternsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false}));
        } else {
            console.error("Unexpected response structure for bot patterns:", response);
            handleApiError({ message: "Received invalid data structure for bot patterns." }, "Failed to fetch bot patterns");
            setBotPatterns([]);
            setBotPatternsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false}));
        }
    } catch (err) {
        handleApiError(err, "Failed to fetch bot patterns");
        setBotPatternsPagination(prev => ({ ...prev, isLoading: false, totalItems: 0}));
        setBotPatterns([]);
    }
  }, [repoId, repository]);
  
  // useEffect for initial load of related data (page 1)
  useEffect(() => {
    if (repository && !isLoadingRepo) { // Ensure repo data is loaded and not still loading
        fetchPaginatedDatasets(1);
        fetchPaginatedModels(1);
        fetchPaginatedTrainingJobs(1);
        fetchPaginatedHpSearchJobs(1);
        fetchPaginatedInferenceJobs(1);
        fetchPaginatedBotPatterns(1);
    }
  }, [repository, isLoadingRepo]); // Rerun if repository object changes

  // useEffects for page changes
  useEffect(() => { if (repository) fetchPaginatedDatasets(datasetsPagination.currentPage); }, [datasetsPagination.currentPage, repository, fetchPaginatedDatasets]);
  useEffect(() => { if (repository) fetchPaginatedModels(modelsPagination.currentPage); }, [modelsPagination.currentPage, repository, fetchPaginatedModels]);
  useEffect(() => { if (repository) fetchPaginatedTrainingJobs(trainingJobsPagination.currentPage); }, [trainingJobsPagination.currentPage, repository, fetchPaginatedTrainingJobs]);
  useEffect(() => { if (repository) fetchPaginatedHpSearchJobs(hpSearchJobsPagination.currentPage); }, [hpSearchJobsPagination.currentPage, repository, fetchPaginatedHpSearchJobs]);
  useEffect(() => { if (repository) fetchPaginatedInferenceJobs(inferenceJobsPagination.currentPage); }, [inferenceJobsPagination.currentPage, repository, fetchPaginatedInferenceJobs]);
  useEffect(() => { if (repository) fetchPaginatedBotPatterns(botPatternsPagination.currentPage); }, [botPatternsPagination.currentPage, repository, fetchPaginatedBotPatterns]);


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

  const getDisplayRepoStatusInfo = () => {
    if (isLoadingRepo && !repository) return { text: "Loading info...", badgeVariant: "outline" as const, icon: <Loader2 className="h-4 w-4 animate-spin" /> };
    if (repoError) return { text: "Error loading", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    if (!repository) return { text: "Not found", badgeVariant: "destructive" as const };

    if (repoIngestionStatus) {
      const { status, status_message, progress } = repoIngestionStatus;
      if (status === "RUNNING" || status === "PENDING") {
        return { 
          text: `${status_message || status} (${progress ?? 0}%)`,
          badgeVariant: "outline" as const,
          icon: <RefreshCw className="h-4 w-4 animate-spin" />
        };
      }
      if (status === "SUCCESS") return { text: "Ingested", badgeVariant: "default" as const , icon: <CheckCircle className="h-4 w-4 text-green-600" /> };
      if (status === "FAILED") return { text: `Ingestion Failed: ${status_message || "Error details unavailable."}`, badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    }
    // Fallback based on repository data if no active/recent task
    // This logic may need refinement based on actual backend states post-ingestion
    return repository.datasets_count > 0 || repository.github_issues_count > 0 || repository.bot_patterns_count > 0 ? 
           { text: "Ingested (Idle)", badgeVariant: "default" as const } : 
           { text: "Ready for Ingestion", badgeVariant: "secondary" as const };
  };
  
  const displayRepoStatus = getDisplayRepoStatusInfo();

  const renderTaskAwareStatusBadge = (taskAwareEntityStatus?: TaskStatusUpdatePayload, fallbackStaticStatus?: string) => {
    const currentStatusToDisplay = taskAwareEntityStatus || (fallbackStaticStatus ? { status: fallbackStaticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusToDisplay) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusToDisplay;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (status?.toUpperCase()) { // Normalize status to uppercase for comparison
      case "SUCCESS":
      case "READY": // For dataset status
        badgeVariant = "default"; 
        icon = <CheckCircle className="h-3 w-3 mr-1" />;
        text = `Completed: ${status_message || "Ready"}`;
        break;
      case "RUNNING":
      case "PENDING":
      case "GENERATING": // For dataset status
        badgeVariant = "outline";
        icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />;
        text = `${status_message || status} (${progress ?? 0}%)`;
        break;
      case "FAILED":
        badgeVariant = "destructive";
        icon = <AlertCircle className="h-3 w-3 mr-1" />;
        text = `Failed: ${status_message || "Error"}`;
        break;
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap">{icon}{text}</Badge>;
  };

  const handleRefreshData = () => {
    toast({title: "Refreshing repository data..."});
    fetchMainRepositoryData(); // This will re-fetch the main repo and then trigger related data fetches
  };

  // Helper for rendering pagination elements
  const renderPaginationControls = (
    currentPage: number,
    totalItems: number,
    limit: number,
    onPageChange: (page: number) => void,
    isLoading: boolean
  ) => {
    const totalPages = Math.ceil(totalItems / limit);
    if (totalPages <= 1) return null;

    // Simplified page number generation
    let pageNumbers: (number | string)[] = [];
    if (totalPages <= 7) {
        pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);
    } else {
        pageNumbers.push(1);
        if (currentPage > 3) pageNumbers.push('...');
        if (currentPage > 2) pageNumbers.push(currentPage - 1);
        if (currentPage > 1 && currentPage < totalPages) pageNumbers.push(currentPage);
        if (currentPage < totalPages -1) pageNumbers.push(currentPage + 1);
        if (currentPage < totalPages - 2) pageNumbers.push('...');
        pageNumbers.push(totalPages);
        pageNumbers = [...new Set(pageNumbers)]; // Remove duplicates if any
    }


    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              onClick={() => onPageChange(currentPage - 1)}
              aria-disabled={currentPage <= 1 || isLoading}
              className={(currentPage <= 1 || isLoading) ? "pointer-events-none opacity-50" : ""}
            />
          </PaginationItem>
          {pageNumbers.map((page, index) => (
            <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}>
              {typeof page === 'number' ? (
                <PaginationLink
                  onClick={() => onPageChange(page)}
                  isActive={currentPage === page}
                  aria-disabled={isLoading}
                  className={isLoading ? "pointer-events-none opacity-50" : ""}
                >
                  {page}
                </PaginationLink>
              ) : (
                <PaginationEllipsis />
              )}
            </PaginationItem>
          ))}
          <PaginationItem>
            <PaginationNext
              onClick={() => onPageChange(currentPage + 1)}
              aria-disabled={currentPage >= totalPages || isLoading}
              className={(currentPage >= totalPages || isLoading) ? "pointer-events-none opacity-50" : ""}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };


  if (isLoadingRepo && !repository && !repoError) {
    return (
      <MainLayout>
        <PageContainer title="Loading Repository..." description="Fetching repository details...">
          <div className="space-y-6">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-10 w-1/3" />
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1,2,3].map(i => <Skeleton key={i} className="h-32" />)}
            </div>
          </div>
        </PageContainer>
      </MainLayout>
    );
  }

  if (repoError || !repository) {
    return (
      <MainLayout>
         <PageContainer
            title="Error"
            description={repoError || "The requested repository could not be found or an error occurred."}
            actions={
                 <Button onClick={() => router.push('/repositories')} variant="outline">
                    <ArrowLeft className="mr-2 h-4 w-4" /> Back to Repositories
                </Button>
            }
        >
           <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                    Please check the repository ID or try again later. If the problem persists, contact support.
                </AlertDescription>
            </Alert>
        </PageContainer>
      </MainLayout>
    );
  }

  const pageActions = (
    <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={handleRefreshData} disabled={isLoadingRepo || datasetsPagination.isLoading || modelsPagination.isLoading /* etc. */}>
            <RefreshCw className={`mr-2 h-4 w-4 ${ (isLoadingRepo || datasetsPagination.isLoading) ? 'animate-spin' : ''}`} />
            Refresh
        </Button>
        <Button size="sm" asChild>
            <Link href={`/repositories/${repoId}/settings`}>
                <Settings className="mr-2 h-4 w-4" /> Settings
            </Link>
        </Button>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer
        title={repository.name}
        description={
          <a href={repository.git_url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline truncate block max-w-full md:max-w-xl lg:max-w-2xl">
            {repository.git_url}
          </a>
        }
        actions={pageActions}
        className="px-4 md:px-6 lg:px-8"
      >
         <div className="mb-4">
            <Badge variant={displayRepoStatus.badgeVariant} className="text-base px-3 py-1">
                {displayRepoStatus.icon && <span className="mr-1.5">{displayRepoStatus.icon}</span>}
                {displayRepoStatus.text}
            </Badge>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="commits">Commits</TabsTrigger>
            <TabsTrigger value="datasets">Datasets ({datasetsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : datasetsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="models">Models ({modelsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : modelsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="jobs">Jobs</TabsTrigger>
            <TabsTrigger value="bot-patterns">Bot Patterns ({botPatternsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : botPatternsPagination.totalItems})</TabsTrigger>
          </TabsList>

          {/* OVERVIEW TAB */}
          <TabsContent value="overview" className="space-y-6">
            {/* ... Overview tab content as previously defined, using states like `datasets`, `models`, etc. for recent items ... */}
            {/* Ensure it uses models.length or jobs.length from their paginated states for counts if needed */}
            <Card>
              <CardHeader><CardTitle>Repository Summary</CardTitle></CardHeader>
              <CardContent className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4 text-sm">
                <div><Label className="text-muted-foreground block mb-0.5">Date Added</Label><p>{formatDate(repository.created_at)}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Last Updated (Metadata)</Label><p>{formatDate(repository.updated_at)}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Last Ingestion Activity</Label><p>{formatDate(repoIngestionStatus?.timestamp || null)}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Datasets Created</Label><p className="font-semibold">{repository.datasets_count}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Bot Patterns (Specific)</Label><p className="font-semibold">{repository.bot_patterns_count}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Linked GitHub Issues</Label><p className="font-semibold">{repository.github_issues_count}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Models Trained</Label><p className="font-semibold">{modelsPagination.isLoading ? <Loader2 className="h-4 w-4 animate-spin inline-block"/> : modelsPagination.totalItems}</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Total Commits</Label><p>N/A</p></div>
                <div><Label className="text-muted-foreground block mb-0.5">Branches</Label><p>N/A</p></div>
              </CardContent>
            </Card>
            
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3">
                      <CardTitle className="text-base">Recent Datasets</CardTitle>
                      {datasetsPagination.totalItems > 3 && <Button variant="link" size="sm" onClick={() => setActiveTab("datasets")} className="text-primary h-auto p-0">View All</Button>}
                  </CardHeader>
                  <CardContent>
                      {datasetsPagination.isLoading && datasets.length === 0 ? <Skeleton className="h-24 w-full"/> : !datasetsPagination.isLoading && datasets.length === 0 ? 
                          <div className="text-center py-4 space-y-2"><p className="text-sm text-muted-foreground">No datasets created yet.</p><Button size="sm" asChild><Link href={`/datasets/create?repository=${repoId}`}><Plus className="mr-2 h-4 w-4" /> Create Dataset</Link></Button></div> :
                          <ul className="space-y-2">
                              {datasets.slice(0,3).map(ds => {
                                  const datasetTask = getLatestTaskForEntity(taskStatuses, "Dataset", ds.id, "dataset_generation");
                                  return (
                                  <li key={ds.id} className="text-sm flex justify-between items-center py-1.5 border-b border-dashed last:border-b-0">
                                      <Link href={`/datasets/${ds.id}`} className="hover:underline font-medium truncate pr-2" title={ds.name}>{ds.name}</Link>
                                      {renderTaskAwareStatusBadge(datasetTask, ds.status)}
                                  </li>
                              )})}
                          </ul>
                      }
                  </CardContent>
              </Card>
              <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3">
                      <CardTitle className="text-base">Recent Jobs</CardTitle>
                        {(trainingJobsPagination.totalItems + hpSearchJobsPagination.totalItems + inferenceJobsPagination.totalItems > 3) && 
                          <Button variant="link" size="sm" onClick={() => setActiveTab("jobs")} className="text-primary h-auto p-0">View All</Button>}
                  </CardHeader>
                  <CardContent>
                      {(trainingJobsPagination.isLoading && hpSearchJobsPagination.isLoading && inferenceJobsPagination.isLoading) && 
                        (trainingJobs.length + hpSearchJobs.length + inferenceJobs.length === 0) ? (
                          <Skeleton className="h-24 w-full"/>
                      ) : 
                        !(trainingJobsPagination.isLoading || hpSearchJobsPagination.isLoading || inferenceJobsPagination.isLoading) && 
                        (trainingJobs.length + hpSearchJobs.length + inferenceJobs.length === 0) ? (
                          <div className="text-center py-4 space-y-2">
                              <p className="text-sm text-muted-foreground">No jobs have been run for this repository yet.</p>
                              <Button size="sm" asChild>
                                  {/* Link to a general jobs page or a "create job" flow for this repo */}
                                  <Link href={`/jobs?repositoryId=${repoId}`}> 
                                      <Play className="mr-2 h-4 w-4" /> Start a Job
                                  </Link>
                              </Button>
                          </div>
                        ) : (
                          <ul className="space-y-3">
                              {/* Display up to 1 recent job from each category for the overview */}
                              {trainingJobs.slice(0,1).map(job => {
                                  const jobTask = getLatestTaskForEntity(taskStatuses, "TrainingJob", job.id, "model_training");
                                  const datasetUsed = datasets.find(d => d.id === job.dataset_id);
                                  return ( 
                                      <li key={`train-${job.id}`} className="text-sm flex justify-between items-center py-1.5 border-b border-dashed last:border-b-0">
                                          <Link href={`/jobs/${job.id}?type=training`} className="hover:underline font-medium truncate pr-2" title={`Train: ${job.config.model_name} on ${datasetUsed?.name || job.dataset_id}`}>
                                              Train: {job.config.model_name.length > 25 ? job.config.model_name.substring(0,25) + "..." : job.config.model_name}
                                          </Link>
                                          {renderTaskAwareStatusBadge(jobTask, job.status)}
                                      </li> 
                                  )
                              })}
                              {hpSearchJobs.slice(0,1).map(job => {
                                    const jobTask = getLatestTaskForEntity(taskStatuses, "HPSearchJob", job.id, "hp_search");
                                    const datasetUsed = datasets.find(d => d.id === job.dataset_id);
                                    return ( 
                                      <li key={`hp-${job.id}`} className="text-sm flex justify-between items-center py-1.5 border-b border-dashed last:border-b-0">
                                          <Link href={`/jobs/${job.id}?type=hp_search`} className="hover:underline font-medium truncate pr-2" title={`HP Search: ${job.optuna_study_name} on ${datasetUsed?.name || job.dataset_id}`}>
                                              HP Search: {job.optuna_study_name.length > 20 ? job.optuna_study_name.substring(0,20) + "..." : job.optuna_study_name}
                                          </Link>
                                          {renderTaskAwareStatusBadge(jobTask, job.status)}
                                      </li>
                                  )
                              })}
                              {inferenceJobs.slice(0,1).map(job => {
                                    const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id /*, "model_inference" or generic */);
                                    const inputRefCommit = typeof job.input_reference === 'object' && job.input_reference.commit_hash ? String(job.input_reference.commit_hash).substring(0,8) : "N/A";
                                    return ( 
                                      <li key={`infer-${job.id}`} className="text-sm flex justify-between items-center py-1.5 border-b border-dashed last:border-b-0">
                                          <Link href={`/prediction-insights/${job.id}`} className="hover:underline font-medium truncate pr-2" title={`Inference for commit ${inputRefCommit} on ${formatDate(job.created_at)}`}>
                                              Inference (Commit: {inputRefCommit}...)
                                          </Link>
                                          {renderTaskAwareStatusBadge(jobTask, job.status)}
                                      </li> 
                                  )
                              })}
                              {/* If all lists are empty after slicing, show a message */}
                              {trainingJobs.slice(0,1).length === 0 && hpSearchJobs.slice(0,1).length === 0 && inferenceJobs.slice(0,1).length === 0 &&
                                !(trainingJobsPagination.isLoading || hpSearchJobsPagination.isLoading || inferenceJobsPagination.isLoading) && (
                                  <li className="text-sm text-muted-foreground text-center py-2">No recent job activity.</li>
                              )}
                          </ul>
                      )}
                  </CardContent>
              </Card>
            </div>
          </TabsContent>
          
          {/* COMMITS TAB */}
          <TabsContent value="commits" className="space-y-4">
            <TabsContent value="commits" className="space-y-4">
            <RepositoryCommitsTab repoId={repoId} repoName={repository.name}/>
          </TabsContent>
          </TabsContent>

          {/* DATASETS TAB with Pagination */}
          <TabsContent value="datasets" className="space-y-4">
            <PageContainer 
                title={`Datasets (${datasetsPagination.isLoading && datasetsPagination.totalItems === 0 ? '...' : datasetsPagination.totalItems})`}
                actions={<Button asChild size="sm"><Link href={`/datasets/create?repository=${repoId}`}><Plus className="mr-2 h-4 w-4"/>Create Dataset</Link></Button>}
            >
                {datasetsPagination.isLoading && datasets.length === 0 ? (
                    <div className="rounded-md border p-4 space-y-2"> {/* Applied to multiple skeletons */}
                        <Skeleton className="h-10 w-full"/>
                        <Skeleton className="h-10 w-full"/>
                        <Skeleton className="h-10 w-full"/>
                    </div>
                ) 
                : !datasetsPagination.isLoading && datasets.length === 0 ? ( 
                    <Card className="text-center py-10">
                        <CardContent className="flex flex-col items-center justify-center">
                            <Database className="h-12 w-12 text-muted-foreground mb-4" />
                            <p className="text-muted-foreground mb-3">No datasets found for this repository.</p>
                            <Button asChild><Link href={`/datasets/create?repository=${repoId}`}><Plus className="mr-2 h-4 w-4" /> Create Your First Dataset</Link></Button>
                        </CardContent>
                    </Card>
                ) 
                : (
                <>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="max-w-xs">Description</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
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
                                            <Link href={`/datasets/${dataset.id}`}>View Details</Link>
                                        </Button>
                                    </TableCell> 
                                </TableRow> 
                            );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  {renderPaginationControls(datasetsPagination.currentPage, datasetsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedDatasets, datasetsPagination.isLoading)}
                  <div className="text-center text-xs text-muted-foreground mt-1">
                    {datasetsPagination.totalItems > 0 ? `Showing ${datasets.length} of ${datasetsPagination.totalItems} datasets` : ""}
                  </div>
                </>
                )}
            </PageContainer>
          </TabsContent>
          
          {/* MODELS TAB with Pagination */}
          <TabsContent value="models" className="space-y-4">
            <PageContainer
                title={`ML Models (${modelsPagination.isLoading && modelsPagination.totalItems === 0 ? '...' : modelsPagination.totalItems})`}
                actions={<Button asChild size="sm"><Link href={`/jobs/train?repositoryId=${repoId}`}><Puzzle className="mr-2 h-4 w-4" /> Train New Model</Link></Button>}
            >
                {modelsPagination.isLoading && models.length === 0 ? (
                    <div className="rounded-md border p-4 space-y-2">
                        <Skeleton className="h-10 w-full"/>
                        <Skeleton className="h-10 w-full"/>
                        <Skeleton className="h-10 w-full"/>
                    </div>
                ) 
                : !modelsPagination.isLoading && models.length === 0 ? ( 
                    <Card className="text-center py-10">
                        <CardContent className="flex flex-col items-center justify-center">
                            <BarChart3 className="h-12 w-12 text-muted-foreground mb-4" />
                            <p className="text-muted-foreground mb-3">No ML models trained with data from this repository.</p>
                            <Button asChild><Link href={`/jobs/train?repositoryId=${repoId}`}><Puzzle className="mr-2 h-4 w-4" /> Train Your First Model</Link></Button>
                        </CardContent>
                    </Card>
                ) 
                : (
                <>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Version</TableHead><TableHead>Type</TableHead><TableHead>Dataset</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {models.map((model) => {
                            const sourceDataset = datasets.find(d => d.id === model.dataset_id);
                            return (
                                <TableRow key={model.id}>
                                    <TableCell className="font-medium break-all">{model.name}</TableCell>
                                    <TableCell>{model.version}</TableCell>
                                    <TableCell><Badge variant="outline">{model.model_type}</Badge></TableCell>
                                    <TableCell>
                                        {sourceDataset ? 
                                            <Link href={`/datasets/${model.dataset_id}`} className="hover:underline">{sourceDataset.name}</Link> 
                                            : model.dataset_id || "N/A"
                                        }
                                    </TableCell>
                                    <TableCell>{formatDate(model.created_at)}</TableCell>
                                    <TableCell className="text-right space-x-2">
                                        <Button variant="outline" size="sm" asChild><Link href={`/models/${model.id}`}>View Model</Link></Button>
                                        <Button variant="secondary" size="sm" asChild><Link href={`/jobs/inference?modelId=${model.id}&repositoryId=${repoId}`}>Run Inference</Link></Button>
                                    </TableCell>
                                </TableRow>
                            )
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  {renderPaginationControls(modelsPagination.currentPage, modelsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedModels, modelsPagination.isLoading)}
                   <div className="text-center text-xs text-muted-foreground mt-1">
                        {modelsPagination.totalItems > 0 ? `Showing ${models.length} of ${modelsPagination.totalItems} models` : ""}
                    </div>
                </>
                )}
            </PageContainer>
          </TabsContent>
          
          {/* JOBS TAB with Pagination for each sub-list */}
          <TabsContent value="jobs" className="space-y-6">
            <PageContainer
                title={`ML Jobs for ${repository.name}`}
                actions={ 
                    <div className="space-x-2">
                        <Button variant="outline" size="sm" asChild><Link href={`/jobs/train?repositoryId=${repoId}`}><Plus className="mr-1 h-3 w-3"/>New Training</Link></Button>
                        <Button variant="outline" size="sm" asChild><Link href={`/jobs/hp-search?repositoryId=${repoId}`}><Plus className="mr-1 h-3 w-3"/>New HP Search</Link></Button>
                    </div>
                }
            >
                {/* Training Jobs Section */}
                <Card>
                  <CardHeader><CardTitle className="text-base">Training Jobs ({trainingJobsPagination.isLoading && trainingJobsPagination.totalItems === 0 ? '...' : trainingJobsPagination.totalItems})</CardTitle></CardHeader>
                  <CardContent>
                  {trainingJobsPagination.isLoading && trainingJobs.length === 0 ? <Skeleton className="h-24 w-full"/> 
                  : !trainingJobsPagination.isLoading && trainingJobs.length === 0 ? <p className="text-sm text-muted-foreground py-2 text-center">No training jobs for this repository.</p> 
                  : (
                    <>
                    <Table>
                      <TableHeader><TableRow><TableHead>Model Name</TableHead><TableHead>Dataset</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {trainingJobs.map(job => {
                            const jobTask = getLatestTaskForEntity(taskStatuses, "TrainingJob", job.id, "model_training");
                            const datasetUsed = datasets.find(d => d.id === job.dataset_id);
                            return(
                            <TableRow key={`train-${job.id}`}>
                                <TableCell className="font-medium break-all">{job.config.model_name}</TableCell>
                                <TableCell>{datasetUsed ? <Link href={`/datasets/${job.dataset_id}`} className="hover:underline">{datasetUsed.name}</Link> : job.dataset_id}</TableCell>
                                <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                                <TableCell>{formatDate(job.created_at)}</TableCell>
                                <TableCell className="text-right space-x-1">
                                    <Button variant="outline" size="sm" asChild>
                                      <Link href={`/jobs/${job.id}?type=training`}>Details</Link>
                                    </Button>
                                    {job.ml_model_id && job.status === JobStatusEnum.SUCCESS && (
                                      <Button variant="link" size="sm" asChild>
                                        <Link href={`/models/${job.ml_model_id}`}>View Model</Link>
                                      </Button>
                                    )}
                                </TableCell>
                            </TableRow>
                        )})}
                      </TableBody>
                    </Table>
                    {renderPaginationControls(trainingJobsPagination.currentPage, trainingJobsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedTrainingJobs, trainingJobsPagination.isLoading)}
                    </>
                  )}
                  </CardContent>
                </Card>
                
                {/* HP Search Jobs Section */}
                <Card>
                  <CardHeader><CardTitle className="text-base">HP Search Jobs ({hpSearchJobsPagination.isLoading && hpSearchJobsPagination.totalItems === 0 ? '...' : hpSearchJobsPagination.totalItems})</CardTitle></CardHeader>
                  <CardContent>
                  {hpSearchJobsPagination.isLoading && hpSearchJobs.length === 0 ? <Skeleton className="h-24 w-full"/> 
                  : !hpSearchJobsPagination.isLoading && hpSearchJobs.length === 0 ? <p className="text-sm text-muted-foreground py-2 text-center">No HP search jobs for this repository.</p> 
                  : (
                    <>
                    <Table>
                      <TableHeader><TableRow><TableHead>Study Name</TableHead><TableHead>Dataset</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {hpSearchJobs.map(job => {
                            const jobTask = getLatestTaskForEntity(taskStatuses, "HPSearchJob", job.id, "hp_search");
                            const datasetUsed = datasets.find(d => d.id === job.dataset_id);
                            return(
                            <TableRow key={`hp-${job.id}`}>
                                <TableCell className="font-medium break-all">{job.optuna_study_name}</TableCell>
                                <TableCell>{datasetUsed ? <Link href={`/datasets/${job.dataset_id}`} className="hover:underline">{datasetUsed.name}</Link> : job.dataset_id}</TableCell>
                                <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                                <TableCell>{formatDate(job.created_at)}</TableCell>
                                <TableCell className="text-right"><Button variant="outline" size="sm" asChild><Link href={`/jobs/${job.id}?type=hp_search`}>Details</Link></Button></TableCell>
                            </TableRow>
                        )})}
                      </TableBody>
                    </Table>
                     {renderPaginationControls(hpSearchJobsPagination.currentPage, hpSearchJobsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedHpSearchJobs, hpSearchJobsPagination.isLoading)}
                    </>
                  )}
                  </CardContent>
                </Card>

                {/* Inference Jobs Section */}
                <Card>
                  <CardHeader><CardTitle className="text-base">Inference Jobs ({inferenceJobsPagination.isLoading && inferenceJobsPagination.totalItems === 0 ? '...' : inferenceJobsPagination.totalItems})</CardTitle></CardHeader>
                  <CardContent>
                  {inferenceJobsPagination.isLoading && inferenceJobs.length === 0 ? <Skeleton className="h-24 w-full"/> 
                  : !inferenceJobsPagination.isLoading && inferenceJobs.length === 0 ? <p className="text-sm text-muted-foreground py-2 text-center">No inference jobs found for models related to this repository.</p> 
                  : (
                    <>
                    <Table>
                      <TableHeader><TableRow><TableHead>Input Ref.</TableHead><TableHead>Model ID</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {inferenceJobs.map(job => {
                            const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id); // No specific job_type for generic inference task status
                            return(
                            <TableRow key={`infer-${job.id}`}>
                                <TableCell className="font-mono text-xs max-w-[150px] sm:max-w-[200px] truncate" title={typeof job.input_reference === 'object' ? JSON.stringify(job.input_reference) : String(job.input_reference)}>
                                    {typeof job.input_reference === 'object' ? (job.input_reference.commit_hash ? `Commit: ${String(job.input_reference.commit_hash).substring(0,8)}...` : JSON.stringify(job.input_reference)) : String(job.input_reference)}
                                </TableCell>
                                <TableCell><Link href={`/models/${job.ml_model_id}`} className="hover:underline">{job.ml_model_id}</Link></TableCell>
                                <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                                <TableCell>{formatDate(job.created_at)}</TableCell>
                                <TableCell className="text-right"><Button variant="outline" size="sm" asChild><Link href={`/prediction-insights/${job.id}`}>Insights</Link></Button></TableCell>
                            </TableRow>
                        )})}
                      </TableBody>
                    </Table>
                    {renderPaginationControls(inferenceJobsPagination.currentPage, inferenceJobsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedInferenceJobs, inferenceJobsPagination.isLoading)}
                    </>
                  )}
                  </CardContent>
                </Card>
            </PageContainer>
          </TabsContent>


          {/* BOT PATTERNS TAB with Pagination */}
          <TabsContent value="bot-patterns" className="space-y-4">
            <PageContainer
                title={`Repository-Specific Bot Patterns (${botPatternsPagination.isLoading && botPatternsPagination.totalItems === 0 ? '...' : botPatternsPagination.totalItems})`}
                description={`Manage bot identification patterns for ${repository.name}. Global patterns will also apply if no specific patterns are defined here.`}
                actions={ 
                    <Button asChild size="sm">
                        <Link href={`/bot-patterns?repository=${repoId}`}>
                            <Settings className="mr-2 h-4 w-4" /> Manage Patterns
                        </Link>
                    </Button>
                }
            >
                {botPatternsPagination.isLoading && botPatterns.length === 0 ? (
                    <div className="rounded-md border p-4 space-y-2">
                        <Skeleton className="h-10 w-full"/>
                        <Skeleton className="h-10 w-full"/>
                    </div>
                ) 
                : !botPatternsPagination.isLoading && botPatterns.length === 0 ? ( 
                <Card className="text-center py-10">
                    <CardContent className="flex flex-col items-center justify-center">
                         <Layers className="h-12 w-12 text-muted-foreground mb-4" />
                        <p className="text-muted-foreground mb-3">No repository-specific bot patterns defined.</p>
                        <Button asChild><Link href={`/bot-patterns?repository=${repoId}`}><Plus className="mr-2 h-4 w-4" /> Add Specific Pattern</Link></Button>
                        <p className="text-xs text-muted-foreground mt-2">
                            <Link href="/bot-patterns" className="hover:underline text-primary">View/Manage Global Patterns</Link>
                        </p>
                    </CardContent>
                </Card>
                ) 
                : (
                <>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader><TableRow><TableHead>Pattern</TableHead><TableHead>Exclusion</TableHead><TableHead className="max-w-md">Description</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {botPatterns.map((pattern) => (
                            <TableRow key={pattern.id}>
                                <TableCell className="font-mono break-all">{pattern.pattern}</TableCell>
                                <TableCell>{pattern.is_exclusion ? "Yes" : "No"}</TableCell>
                                <TableCell className="max-w-md truncate" title={pattern.description || ""}>{pattern.description || "N/A"}</TableCell>
                            </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  {renderPaginationControls(botPatternsPagination.currentPage, botPatternsPagination.totalItems, ITEMS_PER_PAGE, fetchPaginatedBotPatterns, botPatternsPagination.isLoading)}
                  <div className="text-center text-xs text-muted-foreground mt-1">
                    {botPatternsPagination.totalItems > 0 ? `Showing ${botPatterns.length} of ${botPatternsPagination.totalItems} patterns` : ""}
                  </div>
                </>
                )}
            </PageContainer>
          </TabsContent>
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}