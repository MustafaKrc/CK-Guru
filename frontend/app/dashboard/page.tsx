// app/dashboard/page.tsx
"use client"

import React, { useState, useEffect, useMemo } from "react";
import { AuthenticatedLayout } from "@/components/layout/authenticated-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, Database, GitBranch, AlertCircle, CheckCircle, Loader2, RefreshCw } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { PageContainer } from "@/components/ui/page-container";
import Link from "next/link";
import { apiService, handleApiError } from "@/lib/apiService";
import { DashboardSummaryStats } from "@/types/api/dashboard";
import { Repository } from "@/types/api/repository";
import { TrainingJobRead } from "@/types/api/training-job";
import { HPSearchJobRead } from "@/types/api/hp-search-job";
import { InferenceJobRead } from "@/types/api/inference-job";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";
import { Alert, AlertDescription } from "@/components/ui/alert"; // Ensure Alert is imported

type RecentJobItem = (TrainingJobRead | HPSearchJobRead | InferenceJobRead) & { jobType: 'Training' | 'HP Search' | 'Inference' };

const RECENT_ITEMS_LIMIT = 3;

export default function DashboardPage() {
  const { user } = useAuth();
  const { taskStatuses } = useTaskStore();

  const [stats, setStats] = useState<DashboardSummaryStats | null>(null);
  const [recentRepositories, setRecentRepositories] = useState<Repository[]>([]);
  const [recentJobs, setRecentJobs] = useState<RecentJobItem[]>([]);
  
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingRecentRepos, setIsLoadingRecentRepos] = useState(true);
  const [isLoadingRecentJobs, setIsLoadingRecentJobs] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setIsLoadingStats(true);
      setIsLoadingRecentRepos(true);
      setIsLoadingRecentJobs(true);
      setError(null);

      try {
        const summaryStatsPromise = apiService.getDashboardSummaryStats();
        const reposPromise = apiService.getRepositories({ limit: RECENT_ITEMS_LIMIT, skip: 0 });
        const trainingJobsPromise = apiService.getTrainingJobs({ limit: RECENT_ITEMS_LIMIT, skip: 0 });
        const hpSearchJobsPromise = apiService.getHpSearchJobs({ limit: RECENT_ITEMS_LIMIT, skip: 0 });
        const inferenceJobsPromise = apiService.getInferenceJobs({ limit: RECENT_ITEMS_LIMIT, skip: 0 });

        const [
          summaryStats, 
          reposResponse, 
          trainingJobsRes, 
          hpSearchJobsRes, 
          inferenceJobsRes
        ] = await Promise.all([
          summaryStatsPromise,
          reposPromise,
          trainingJobsPromise,
          hpSearchJobsPromise,
          inferenceJobsPromise
        ]);

        setStats(summaryStats);
        setIsLoadingStats(false);

        setRecentRepositories(reposResponse.items || []);
        setIsLoadingRecentRepos(false);
        
        const combinedJobs: RecentJobItem[] = [
          ...(trainingJobsRes.items || []).map(job => ({ ...job, jobType: 'Training' as const })),
          ...(hpSearchJobsRes.items || []).map(job => ({ ...job, jobType: 'HP Search' as const })),
          ...(inferenceJobsRes.items || []).map(job => ({ ...job, jobType: 'Inference' as const }))
        ];
        
        combinedJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setRecentJobs(combinedJobs.slice(0, RECENT_ITEMS_LIMIT));
        setIsLoadingRecentJobs(false);

      } catch (err) {
        const defaultMessage = "Failed to load dashboard data. Some sections may be unavailable.";
        handleApiError(err, defaultMessage); 
        setError(defaultMessage);
        // Set all loading states to false on global error
        setIsLoadingStats(false);
        setIsLoadingRecentRepos(false);
        setIsLoadingRecentJobs(false);
      }
    };

    fetchDashboardData();
  }, []);

  const formatDate = (dateString?: string | Date | null): string => {
    if (!dateString) return "N/A";
    const date = typeof dateString === 'string' ? new Date(dateString) : dateString;
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const getRepoIngestionStatusText = (repo: Repository) => {
    const task = getLatestTaskForEntity(taskStatuses, "Repository", repo.id, "repository_ingestion");
    if (task && (task.status.toUpperCase() === "RUNNING" || task.status.toUpperCase() === "PENDING")) {
      return "Ingesting";
    }
    // Heuristic: if datasets exist, assume it has been ingested at least once.
    return repo.datasets_count > 0 || repo.github_issues_count > 0 ? "Ingested" : "Not Ingested";
  };

  const getJobStatusBadge = (job: RecentJobItem) => {
    let entityType: "TrainingJob" | "HPSearchJob" | "InferenceJob";
    let taskJobType: string | undefined;

    switch(job.jobType) {
        case "Training": entityType = "TrainingJob"; taskJobType = "model_training"; break;
        case "HP Search": entityType = "HPSearchJob"; taskJobType = "hp_search"; break;
        case "Inference": entityType = "InferenceJob"; taskJobType = "model_inference"; break;
        default: return <Badge variant="secondary">Unknown</Badge>;
    }
    
    const liveTask = getLatestTaskForEntity(taskStatuses, entityType, job.id, taskJobType);
    const displayStatus = liveTask?.status || job.status;
    const displayMessage = liveTask?.status_message || (job as any).status_message;
    const progress = liveTask?.progress;

    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let textToShow = String(displayStatus).toUpperCase(); // Default text

    // Standardize by converting to lower case for comparison with enum values
    switch (String(displayStatus).toLowerCase()) {
      case JobStatusEnum.SUCCESS: badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; textToShow = "Success"; break;
      case JobStatusEnum.RUNNING:
      case JobStatusEnum.STARTED:
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; textToShow = `${displayMessage || displayStatus} (${progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING:
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; textToShow = "Pending"; break;
      case JobStatusEnum.FAILED:
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; textToShow = "Failed"; break;
      case JobStatusEnum.REVOKED:
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; textToShow = "Revoked"; break;
    }
    return <Badge variant={badgeVariant} title={displayMessage || String(displayStatus)}>{icon}{textToShow}</Badge>;
  };
  
  const getJobName = (job: RecentJobItem): string => {
    if (job.jobType === 'Training') return (job as TrainingJobRead).config.model_name || 'Training Job';
    if (job.jobType === 'HP Search') return (job as HPSearchJobRead).optuna_study_name || 'HP Search Job';
    if (job.jobType === 'Inference') {
        const inputRef = (job as InferenceJobRead).input_reference;
        const commitHash = inputRef?.commit_hash ? String(inputRef.commit_hash).substring(0,7) : 'N/A';
        return `Inference (commit ${commitHash})`;
    }
    return 'Unknown Job';
  };
  
  const getJobLink = (job: RecentJobItem): string => {
    if (job.jobType === 'Training') return `/jobs/${job.id}?type=training`;
    if (job.jobType === 'HP Search') return `/jobs/${job.id}?type=hp_search`;
    if (job.jobType === 'Inference') return `/prediction-insights/${job.id}`;
    return "/jobs";
  };

  return (
    <AuthenticatedLayout>
      <PageContainer
        title={user ? `Welcome, ${user.name}` : "Welcome"}
        description="Here's an overview of your software defect prediction projects."
        actions={
          <Button asChild>
            <Link href="/repositories">View All Repositories</Link>
          </Button>
        }
      >
        {error && <Alert variant="destructive" className="mb-4"><AlertCircle className="h-4 w-4" /> <AlertDescription>{error}</AlertDescription></Alert>}
        
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card className="metric-card border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Repositories</CardTitle>
              <GitBranch className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              {isLoadingStats ? <Skeleton className="h-7 w-12 mb-1" /> : <div className="text-2xl font-bold">{stats?.total_repositories ?? <Skeleton className="h-7 w-10 inline-block"/>}</div>}
              {isLoadingStats ? <Skeleton className="h-4 w-3/4" /> : <p className="text-xs text-muted-foreground">{stats?.active_ingestion_tasks ?? 0} active ingestion tasks</p>}
            </CardContent>
          </Card>
          <Card className="metric-card-alt border-accent/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Datasets</CardTitle>
              <Database className="h-4 w-4 text-accent" />
            </CardHeader>
            <CardContent>
              {isLoadingStats ? <Skeleton className="h-7 w-12 mb-1" /> : <div className="text-2xl font-bold">{stats?.total_datasets ?? <Skeleton className="h-7 w-10 inline-block"/>}</div>}
              {isLoadingStats ? <Skeleton className="h-4 w-3/4" /> : 
                <p className="text-xs text-muted-foreground">
                  {stats?.datasets_by_status.ready ?? 0} ready, {stats?.active_dataset_generation_tasks ?? 0} processing
                </p>
              }
            </CardContent>
          </Card>
          <Card className="metric-card border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">ML Models</CardTitle>
              <BarChart3 className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              {isLoadingStats ? <Skeleton className="h-7 w-12 mb-1" /> : <div className="text-2xl font-bold">{stats?.total_ml_models ?? <Skeleton className="h-7 w-10 inline-block"/>}</div>}
              {isLoadingStats ? <Skeleton className="h-4 w-3/4" /> : 
                <p className="text-xs text-muted-foreground">
                  Avg. F1: {stats?.average_f1_score_ml_models?.toFixed(2) ?? 'N/A'} ({stats?.active_ml_jobs ?? 0} active jobs)
                </p>
              }
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Repositories</CardTitle>
              <CardDescription>Your most recently added or updated repositories.</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingRecentRepos ? (
                <div className="space-y-4">{[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full"/>)}</div>
              ) : recentRepositories.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No repositories added yet.</p>
              ) : (
                <div className="space-y-3">
                  {recentRepositories.map((repo) => (
                    <div key={repo.id} className="flex items-center justify-between text-sm p-2 border-b last:border-b-0">
                      <div>
                        <Link href={`/repositories/${repo.id}`} className="font-medium hover:underline">{repo.name}</Link>
                        <p className="text-xs text-muted-foreground">Added: {formatDate(repo.created_at)}</p>
                      </div>
                      <Badge variant={getRepoIngestionStatusText(repo) === "Ingesting" ? "outline" : (getRepoIngestionStatusText(repo) === "Ingested" ? "default" : "secondary")} className="text-xs">
                        {getRepoIngestionStatusText(repo) === "Ingesting" && <RefreshCw className="h-3 w-3 mr-1 animate-spin" />}
                        {getRepoIngestionStatusText(repo)}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Recent Jobs</CardTitle>
              <CardDescription>Your most recent ML and data processing activities.</CardDescription>
            </CardHeader>
            <CardContent>
            {isLoadingRecentJobs ? (
                <div className="space-y-4">{[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full"/>)}</div>
              ) : recentJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No recent job activity.</p>
              ) : (
                <div className="space-y-3">
                  {recentJobs.map((job) => (
                    <div key={`${job.jobType}-${job.id}`} className="flex items-center justify-between text-sm p-2 border-b last:border-b-0">
                      <div>
                        <Link href={getJobLink(job)} className="font-medium hover:underline">
                            {getJobName(job)}
                        </Link>
                        <p className="text-xs text-muted-foreground">
                          {job.jobType} • Created: {formatDate(job.created_at)}
                        </p>
                      </div>
                      {getJobStatusBadge(job)}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </PageContainer>
    </AuthenticatedLayout>
  );
}