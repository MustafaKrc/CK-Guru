// frontend/app/jobs/[id]/page.tsx
"use client";

import React, { useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  RefreshCw,
  Database,
  BarChart3,
  Puzzle,
  Layers,
  Settings,
  Play,
  Eye,
  AlertCircle,
  Loader2,
  CheckCircle,
  Cog,
  FileJson,
  StopCircle,
  FileText,
  Brain,
  CalendarDays,
  Target,
  ListChecks,
  Thermometer,
  SearchCode,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { KeyValueDisplay } from "@/components/ui/KeyValueDisplay";

import { apiService, handleApiError } from "@/lib/apiService";
import { TrainingJobRead, TrainingRunConfig } from "@/types/api/training-job";
import { HPSearchJobRead, HPSearchConfig, HPSuggestion } from "@/types/api/hp-search-job";
import { TaskResponse } from "@/types/api/task";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";
import { PageLoader } from "@/components/ui/page-loader"; // Added import

type JobDetails = TrainingJobRead | HPSearchJobRead;
type JobType = "training" | "hp_search";

// Helper function to format dates
function formatDate(dateString?: string | Date | null): string {
  if (!dateString) return "N/A";
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function JobDetailPageContent() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const jobId = params.id;
  const jobTypeParam = searchParams.get("type") as JobType | null;

  const [jobDetails, setJobDetails] = useState<JobDetails | null>(null);
  const [jobType, setJobType] = useState<JobType | null>(jobTypeParam);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);

  const { taskStatuses } = useTaskStore();

  const fetchJobDetails = useCallback(async () => {
    if (!jobId || !jobType) {
      if (!jobTypeParam) setError("Job type parameter is missing in URL.");
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      let data;
      if (jobType === "training") {
        data = await apiService.get<TrainingJobRead>(`/ml/train/${jobId}`);
      } else if (jobType === "hp_search") {
        data = await apiService.get<HPSearchJobRead>(`/ml/search/${jobId}`);
      } else {
        throw new Error("Invalid job type specified.");
      }
      setJobDetails(data);
    } catch (err) {
      handleApiError(err, `Failed to fetch ${jobType} job details`);
      setError(err instanceof Error ? err.message : "Job not found or error loading.");
      setJobDetails(null);
    } finally {
      setIsLoading(false);
    }
  }, [jobId, jobType, jobTypeParam]);

  useEffect(() => {
    if (jobTypeParam) {
      setJobType(jobTypeParam); // Set jobType from URL param initially
      fetchJobDetails();
    } else if (!jobType && jobId) {
      // Attempt to infer if not provided and not already inferred
      // This simple inference is not robust. Prefer query param.
      // For now, we'll rely on the query param primarily.
      setError("Job type (e.g., ?type=training) must be specified in the URL.");
      setIsLoading(false);
    }
  }, [jobId, jobTypeParam, fetchJobDetails, jobType]);

  // Live status updates via SSE
  const liveJobStatus = useMemo(() => {
    if (!jobDetails || !jobType) return undefined;
    const entityType = jobType === "training" ? "TrainingJob" : "HPSearchJob";
    const taskJobType = jobType === "training" ? "model_training" : "hp_search";
    return getLatestTaskForEntity(taskStatuses, entityType, jobDetails.id, taskJobType);
  }, [taskStatuses, jobDetails, jobType]);

  const effectiveStatus = liveJobStatus?.status || jobDetails?.status;
  const effectiveStatusMessage = liveJobStatus?.status_message || jobDetails?.status_message;
  const effectiveProgress =
    liveJobStatus?.progress ?? (effectiveStatus === JobStatusEnum.SUCCESS ? 100 : 0);

  const handleRefresh = () => {
    toast({ title: "Refreshing job details..." });
    fetchJobDetails();
  };

  const handleRevokeJob = async () => {
    if (!jobDetails?.celery_task_id) {
      toast({
        title: "Error",
        description: "No Celery task ID found for this job.",
        variant: "destructive",
      });
      return;
    }
    setIsRevoking(true);
    try {
      await apiService.post(`/tasks/${jobDetails.celery_task_id}/revoke`);
      toast({
        title: "Revocation Sent",
        description: "Attempting to revoke the job. Status will update.",
      });
      // SSE should update the status, or poll fetchJobDetails after a delay
      setTimeout(fetchJobDetails, 2000); // Refresh after a bit
    } catch (err) {
      handleApiError(err, "Failed to revoke job");
    } finally {
      setIsRevoking(false);
    }
  };

  const getStatusBadge = () => {
    if (isLoading && !jobDetails)
      return (
        <Badge variant="outline">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          Loading...
        </Badge>
      );
    if (!effectiveStatus) return <Badge variant="secondary">Unknown</Badge>;

    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = effectiveStatusMessage || String(effectiveStatus).toUpperCase();

    switch (
      String(effectiveStatus)
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
        badgeVariant = "outline";
        icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />;
        text = `Running (${effectiveProgress}%)`;
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
        icon = <StopCircle className="h-3 w-3 mr-1" />;
        text = "Revoked";
        break;
    }
    return (
      <Badge variant={badgeVariant}>
        {icon}
        {text}
      </Badge>
    );
  };

  if (isLoading && !jobDetails && !error) {
    return (
      <MainLayout>
        <PageContainer title="Loading Job Details..." description="Fetching job information...">
          <Skeleton className="h-10 w-1/3 mb-4" />
          <div className="space-y-6">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-60 w-full" />
          </div>
        </PageContainer>
      </MainLayout>
    );
  }

  if (error || !jobDetails) {
    return (
      <MainLayout>
        <PageContainer
          title="Job Not Found or Error"
          description={error || "The requested job could not be found or an error occurred."}
          actions={
            <Button onClick={() => router.back()} variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
          }
        >
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Please check the job ID and type parameter, or try again later.
            </AlertDescription>
          </Alert>
        </PageContainer>
      </MainLayout>
    );
  }

  const pageTitle =
    jobType === "training"
      ? `Training Job: ${(jobDetails as TrainingJobRead).config.model_name}`
      : `HP Search: ${(jobDetails as HPSearchJobRead).optuna_study_name}`;
  const isJobActive =
    effectiveStatus === JobStatusEnum.RUNNING || effectiveStatus === JobStatusEnum.PENDING;

  const pageActions = (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
        <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} /> Refresh
      </Button>
      {isJobActive && jobDetails.celery_task_id && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" size="sm" disabled={isRevoking}>
              {isRevoking ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <StopCircle className="mr-2 h-4 w-4" />
              )}
              Revoke Job
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirm Revoke</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to attempt to revoke this job? This may not always be
                successful if the task has already started certain operations.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isRevoking}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleRevokeJob} disabled={isRevoking}>
                {isRevoking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Revoking...
                  </>
                ) : (
                  "Revoke"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );

  return (
    <MainLayout>
      <PageContainer
        title={pageTitle}
        description={
          <div className="flex items-center gap-2">
            Job ID: <span className="font-mono">{jobDetails.id}</span> {getStatusBadge()}
          </div>
        }
        actions={pageActions}
      >
        {/* Progress Bar for active jobs */}
        {isJobActive && (
          <div className="mb-4">
            <Label className="text-xs text-muted-foreground">
              {effectiveStatusMessage || "Processing..."}
            </Label>
            <Progress
              value={effectiveProgress}
              className="w-full h-2 mt-1"
              indicatorClassName={
                effectiveStatus === JobStatusEnum.PENDING ? "bg-yellow-500" : "bg-primary"
              }
            />
          </div>
        )}

        {/* Error display */}
        {effectiveStatus === JobStatusEnum.FAILED && effectiveStatusMessage && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{effectiveStatusMessage}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Column 1: Overview & Source */}
          <div className="md:col-span-1 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center">
                  <FileText className="mr-2 h-4 w-4 text-primary" />
                  Job Overview
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div>
                  <Label className="text-muted-foreground">Job Type</Label>
                  <p>{jobType === "training" ? "Model Training" : "Hyperparameter Search"}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Status</Label>
                  <div className="mt-1">{getStatusBadge()}</div>
                </div>
                {effectiveStatusMessage && (
                  <div>
                    <Label className="text-muted-foreground">Status Message</Label>
                    <p className="text-xs break-all">{effectiveStatusMessage}</p>
                  </div>
                )}
                <div>
                  <Label className="text-muted-foreground">Celery Task ID</Label>
                  <p className="font-mono text-xs break-all">
                    {jobDetails.celery_task_id || "N/A"}
                  </p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Created</Label>
                  <p>
                    <CalendarDays className="inline h-3.5 w-3.5 mr-1 text-muted-foreground" />
                    {formatDate(jobDetails.created_at)}
                  </p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Started</Label>
                  <p>
                    <CalendarDays className="inline h-3.5 w-3.5 mr-1 text-muted-foreground" />
                    {formatDate(jobDetails.started_at)}
                  </p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Completed</Label>
                  <p>
                    <CalendarDays className="inline h-3.5 w-3.5 mr-1 text-muted-foreground" />
                    {formatDate(jobDetails.completed_at)}
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center">
                  <Database className="mr-2 h-4 w-4 text-primary" />
                  Source Dataset
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Button variant="link" asChild className="p-0 h-auto text-sm">
                  <Link href={`/datasets/${jobDetails.dataset_id}`}>
                    View Dataset (ID: {jobDetails.dataset_id})
                  </Link>
                </Button>
                {/* TODO: Fetch and display dataset name if needed */}
              </CardContent>
            </Card>
            {jobType === "training" && (jobDetails as TrainingJobRead).ml_model_id && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center">
                    <Brain className="mr-2 h-4 w-4 text-primary" />
                    Resulting Model
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Button variant="link" asChild className="p-0 h-auto text-sm">
                    <Link href={`/models/${(jobDetails as TrainingJobRead).ml_model_id}`}>
                      View Model (ID: {(jobDetails as TrainingJobRead).ml_model_id})
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}
            {jobType === "hp_search" && (jobDetails as HPSearchJobRead).best_ml_model_id && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center">
                    <Brain className="mr-2 h-4 w-4 text-primary" />
                    Best Model from Search
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Button variant="link" asChild className="p-0 h-auto text-sm">
                    <Link href={`/models/${(jobDetails as HPSearchJobRead).best_ml_model_id}`}>
                      View Model (ID: {(jobDetails as HPSearchJobRead).best_ml_model_id})
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Column 2: Configuration Details */}
          <div className="md:col-span-2 space-y-6">
            <KeyValueDisplay
              data={
                jobType === "hp_search"
                  // Exclude hp_space from config for hp_search jobs
                  ? Object.fromEntries(
                      Object.entries((jobDetails as HPSearchJobRead).config).filter(
                        ([key]) => key !== "hp_space"
                      )
                    )
                  : (jobDetails.config as Record<string, any>)
              }
              title="Job Configuration"
              icon={<Cog className="mr-2 h-4 w-4 text-primary" />}
              scrollAreaMaxHeight="max-h-[1200px]"
            />

            {jobType === "hp_search" && (jobDetails as HPSearchJobRead).config.hp_space && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center">
                    <SearchCode className="mr-2 h-4 w-4 text-primary" />
                    Hyperparameter Search Space
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-72">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Param Name</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Range/Choices</TableHead>
                          <TableHead>Step</TableHead>
                          <TableHead>Log</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(jobDetails as HPSearchJobRead).config.hp_space.map((s) => (
                          <TableRow key={s.param_name}>
                            <TableCell className="font-mono">{s.param_name}</TableCell>
                            <TableCell>
                              <Badge variant="secondary">{s.suggest_type}</Badge>
                            </TableCell>
                            <TableCell>
                              {s.choices ? s.choices.join(", ") : `${s.low} - ${s.high}`}
                            </TableCell>
                            <TableCell>{s.step ?? "N/A"}</TableCell>
                            <TableCell>{s.log ? "Yes" : "No"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </ScrollArea>
                </CardContent>
              </Card>
            )}

            {jobType === "hp_search" && (jobDetails as HPSearchJobRead).best_params && (
              <KeyValueDisplay
                data={(jobDetails as HPSearchJobRead).best_params}
                title="Best Hyperparameters Found"
                icon={<Thermometer className="mr-2 h-4 w-4 text-primary" />}
                scrollAreaMaxHeight="max-h-[250px]"
              />
            )}
            {jobType === "hp_search" &&
              (jobDetails as HPSearchJobRead).best_value !== null &&
              (jobDetails as HPSearchJobRead).best_value !== undefined && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center">
                      <Target className="mr-2 h-4 w-4 text-primary" />
                      Best Objective Value
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">
                      {(jobDetails as HPSearchJobRead).best_value?.toFixed(4)}
                    </p>
                  </CardContent>
                </Card>
              )}
          </div>
        </div>
      </PageContainer>
    </MainLayout>
  );
}

export default function JobDetailPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading job details..." />}>
      <JobDetailPageContent />
    </Suspense>
  );
}