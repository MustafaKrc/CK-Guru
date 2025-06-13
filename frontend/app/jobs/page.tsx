// frontend/app/jobs/page.tsx
"use client";

import React, {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

/* -------------------------------------------------------------------------------------------------
 * Shared UI components
 * ------------------------------------------------------------------------------------------------*/
import { MainLayout } from "@/components/main-layout";

import { PageLoader } from "@/components/ui/page-loader";

/* -------------------------------------------------------------------------------------------------
 * Icons
 * ------------------------------------------------------------------------------------------------*/
import {
  AlertCircle,
  ArrowUpDown,
  CheckCircle,
  Loader2,
  MoreHorizontal,
  Puzzle,
  RefreshCw,
  StopCircle,
  Eye,
} from "lucide-react";

/* -------------------------------------------------------------------------------------------------
 * API helpers & hooks
 * ------------------------------------------------------------------------------------------------*/
import { apiService, handleApiError } from "@/lib/apiService";
import { useDebounce } from "@/hooks/useDebounce";
import { toast } from "@/components/ui/use-toast";
import { useTaskStore } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";

/* -------------------------------------------------------------------------------------------------
 * API types
 * ------------------------------------------------------------------------------------------------*/
import {
  HPSearchJobRead,
  PaginatedHPSearchJobRead
} from "@/types/api/hp-search-job";
import { InferenceJobRead, PaginatedInferenceJobRead } from "@/types/api/inference-job";
import { TrainingJobRead, PaginatedTrainingJobRead } from "@/types/api/training-job";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";
import { JobStatusEnum } from "@/types/api/enums";
import { TaskStatusUpdatePayload } from "@/store/taskStore";

/* -------------------------------------------------------------------------------------------------
 * Dialog for cancelling tasks
 * ------------------------------------------------------------------------------------------------*/
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Pagination, PaginationItem, PaginationLink, PaginationContent, PaginationPrevious, PaginationEllipsis, PaginationNext } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PageContainer } from "@/components/ui/page-container";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/* -------------------------------------------------------------------------------------------------
 * Constants & utility types
 * ------------------------------------------------------------------------------------------------*/
const ITEMS_PER_PAGE = 10;
const ALL_FILTER_VALUE = "_all_";

type JobTypeKey = "training" | "hpSearch" | "inference";

type SortableKeys<T extends JobTypeKey> =
  T extends "training"
    ? "name" | "status" | "created_at"
    : T extends "hpSearch"
    ? "name" | "status" | "created_at"
    : "created_at" | "status";

type SortConfig<T extends JobTypeKey> = {
  key: SortableKeys<T>;
  direction: "asc" | "desc";
};

type JobPaginationState = {
  currentPage: number;
  totalItems: number;
  isLoading: boolean;
};

/* -------------------------------------------------------------------------------------------------
 * JobTable – single source of truth for table rows **and** pagination
 * ------------------------------------------------------------------------------------------------*/
interface JobTableProps<T> {
  columns: {
    header: React.ReactNode;
    accessor: (job: T) => React.ReactNode;
    className?: string;
  }[];
  data: T[];
  isLoading: boolean;
  error: string | null;
  paginationState: JobPaginationState;
  onPageChange: (newPage: number) => void;
  entityType: JobTypeKey;
  onCancelJob?: (job: {
    id: number | string;
    celeryTaskId?: string | null;
    name: string;
  }) => void;
}

function JobTable<T extends Record<string, any>>({
  columns,
  data,
  isLoading,
  error,
  paginationState,
  onPageChange,
  entityType,
  onCancelJob
}: JobTableProps<T>) {
  /* ----------------------------------------------------------------------------
   * Internal helper: renderPagination (was previously outside of JobTable)
   * --------------------------------------------------------------------------*/
  const renderPagination = () => {
    const totalPages = Math.ceil(paginationState.totalItems / ITEMS_PER_PAGE);
    if (totalPages <= 1) return null;

    const pages: (number | string)[] = [];
    if (totalPages <= 7) {
      for (let p = 1; p <= totalPages; p++) pages.push(p);
    } else {
      pages.push(1);
      if (paginationState.currentPage > 3) pages.push("…");
      if (paginationState.currentPage > 2) pages.push(paginationState.currentPage - 1);
      if (paginationState.currentPage > 1 && paginationState.currentPage < totalPages)
        pages.push(paginationState.currentPage);
      if (paginationState.currentPage < totalPages - 1)
        pages.push(paginationState.currentPage + 1);
      if (paginationState.currentPage < totalPages - 2) pages.push("…");
      pages.push(totalPages);
    }

    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              aria-disabled={paginationState.currentPage <= 1 || paginationState.isLoading}
              className={
                paginationState.currentPage <= 1 ? "pointer-events-none opacity-50" : ""
              }
              onClick={() => onPageChange(paginationState.currentPage - 1)}
            />
          </PaginationItem>
          {pages.map((p, i) => (
            <PaginationItem key={i}>
              {typeof p === "number" ? (
                <PaginationLink
                  isActive={p === paginationState.currentPage}
                  onClick={() => onPageChange(p)}
                >
                  {p}
                </PaginationLink>
              ) : (
                <PaginationEllipsis />
              )}
            </PaginationItem>
          ))}
          <PaginationItem>
            <PaginationNext
              aria-disabled={
                paginationState.currentPage >= totalPages || paginationState.isLoading
              }
              className={
                paginationState.currentPage >= totalPages
                  ? "pointer-events-none opacity-50"
                  : ""
              }
              onClick={() => onPageChange(paginationState.currentPage + 1)}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  /* ----------------------------------------------------------------------------
   * Early‑return states: loading / error / empty
   * --------------------------------------------------------------------------*/
  if (isLoading && data.length === 0) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!isLoading && data.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No jobs found matching your criteria.
      </p>
    );
  }

  /* ----------------------------------------------------------------------------
   * Table rows + actions
   * --------------------------------------------------------------------------*/
  const renderActions = (job: any) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-7 w-7">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Actions</DropdownMenuLabel>

        {/* view details / insights */}
        {entityType !== "inference" ? (
          <DropdownMenuItem asChild>
            <Link
              href={`/jobs/${job.id}?type=${
                entityType === "hpSearch" ? "hp_search" : entityType
              }`}
            >
              <Eye className="mr-2 h-4 w-4" /> View Details
            </Link>
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem
            asChild
            disabled={job.status !== JobStatusEnum.SUCCESS}
          >
            <Link href={`/prediction-insights/${job.id}`}>
              <Eye className="mr-2 h-4 w-4" /> View Insights
            </Link>
          </DropdownMenuItem>
        )}

        {/* cancel */}
        {onCancelJob &&
          (job.status === JobStatusEnum.RUNNING ||
            job.status === JobStatusEnum.PENDING) &&
          job.celery_task_id && (
            <DropdownMenuItem
              onClick={() =>
                onCancelJob({
                  id: job.id,
                  celeryTaskId: job.celery_task_id,
                  name:
                    job.config?.model_name ||
                    job.optuna_study_name ||
                    `Inference ${job.id}`
                })
              }
            >
              <StopCircle className="mr-2 h-4 w-4 text-destructive" /> Cancel
              Job
            </DropdownMenuItem>
          )}

        {/* view model  */}
        {entityType === "training" &&
          job.ml_model_id &&
          job.status === JobStatusEnum.SUCCESS && (
            <DropdownMenuItem asChild>
              <Link href={`/models/${job.ml_model_id}`}>
                <Puzzle className="mr-2 h-4 w-4" /> View Resulting Model
              </Link>
            </DropdownMenuItem>
          )}
        {entityType === "hpSearch" &&
          job.best_ml_model_id &&
          job.status === JobStatusEnum.SUCCESS && (
            <DropdownMenuItem asChild>
              <Link href={`/models/${job.best_ml_model_id}`}>
                <Puzzle className="mr-2 h-4 w-4" /> View Best Model
              </Link>
            </DropdownMenuItem>
          )}
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map(col => (
                <TableHead key={String(col.header)}>{col.header}</TableHead>
              ))}
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map(job => (
              <TableRow key={`${entityType}-${job.id}`}>
                {columns.map(col => (
                  <TableCell
                    key={String(col.header)}
                    className={`text-xs ${col.className ?? ""}`}
                  >
                    {col.accessor(job)}
                  </TableCell>
                ))}
                <TableCell className="text-right">{renderActions(job)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {renderPagination()}
    </>
  );
}

/* -------------------------------------------------------------------------------------------------
 * JobsPageContent – keeps state/fetching, now DRY with JobTable for UI
 * ------------------------------------------------------------------------------------------------*/
function JobsPageContent() {
  /* ---------------- URL & tab state ---------------- */
  const searchParamsHook = useSearchParams();
  const initialTab = (searchParamsHook.get("tab") as JobTypeKey) || "training";
  const [activeTab, setActiveTab] = useState<JobTypeKey>(initialTab);

  /* ---------------- job data ---------------- */
  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);

  /* ---------------- pagination ---------------- */
  const [trainingPag, setTrainingPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });
  const [hpPag, setHpPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });
  const [infPag, setInfPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });

  /* ---------------- error ---------------- */
  const [trainingErr, setTrainingErr] = useState<string | null>(null);
  const [hpErr, setHpErr] = useState<string | null>(null);
  const [infErr, setInfErr] = useState<string | null>(null);

  /* ---------------- filters & sort ---------------- */
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 500);
  const [statusFilter, setStatusFilter] = useState<string>(ALL_FILTER_VALUE);
  const [datasetFilter, setDatasetFilter] = useState<string>(ALL_FILTER_VALUE);

  const [trainingSort, setTrainingSort] = useState<SortConfig<"training">>({ key: "created_at", direction: "desc" });
  const [hpSort, setHpSort] = useState<SortConfig<"hpSearch">>({ key: "created_at", direction: "desc" });
  const [infSort, setInfSort] = useState<SortConfig<"inference">>({ key: "created_at", direction: "desc" });

  const { taskStatuses } = useTaskStore();

  /* ---------------- datasets for filter ---------------- */
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiService.get<PaginatedDatasetRead>(
          "/datasets?skip=0&limit=1000"
        );
        setDatasets(res.items || []);
      } catch (err) {
        handleApiError(err, "Failed to fetch datasets");
      } finally {
        setIsLoadingDatasets(false);
      }
    })();
  }, []);

  /* ---------------- fetchers ---------------- */
  const fetchTraining = useCallback(
    async (page: number) => {
      setTrainingPag(prev => ({ ...prev, isLoading: true, currentPage: page }));
      setTrainingErr(null);

      const params = new URLSearchParams({
        skip: ((page - 1) * ITEMS_PER_PAGE).toString(),
        limit: ITEMS_PER_PAGE.toString()
      });
      if (statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
      if (datasetFilter !== ALL_FILTER_VALUE) params.append("dataset_id", datasetFilter);
      if (debouncedSearch) params.append("q", debouncedSearch);

      try {
        const res = await apiService.get<PaginatedTrainingJobRead>(
          `/ml/train?${params.toString()}`
        );
        setTrainingJobs(res.items || []);
        setTrainingPag(prev => ({ ...prev, totalItems: res.total || 0, isLoading: false }));
      } catch (err) {
        handleApiError(err, "Failed to fetch training jobs");
        setTrainingErr(err instanceof Error ? err.message : "Error");
        setTrainingPag(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    },
    [statusFilter, datasetFilter, debouncedSearch]
  );

  const fetchHp = useCallback(
    async (page: number) => {
      setHpPag(prev => ({ ...prev, isLoading: true, currentPage: page }));
      setHpErr(null);

      const params = new URLSearchParams({
        skip: ((page - 1) * ITEMS_PER_PAGE).toString(),
        limit: ITEMS_PER_PAGE.toString()
      });
      if (statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
      if (datasetFilter !== ALL_FILTER_VALUE) params.append("dataset_id", datasetFilter);
      if (debouncedSearch) params.append("study_name", debouncedSearch);

      try {
        const res = await apiService.get<PaginatedHPSearchJobRead>(
          `/ml/search?${params.toString()}`
        );
        setHpSearchJobs(res.items || []);
        setHpPag(prev => ({ ...prev, totalItems: res.total || 0, isLoading: false }));
      } catch (err) {
        handleApiError(err, "Failed to fetch HP search jobs");
        setHpErr(err instanceof Error ? err.message : "Error");
        setHpPag(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    },
    [statusFilter, datasetFilter, debouncedSearch]
  );

  const fetchInf = useCallback(
    async (page: number) => {
      setInfPag(prev => ({ ...prev, isLoading: true, currentPage: page }));
      setInfErr(null);

      const params = new URLSearchParams({
        skip: ((page - 1) * ITEMS_PER_PAGE).toString(),
        limit: ITEMS_PER_PAGE.toString()
      });
      if (statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
      if (datasetFilter !== ALL_FILTER_VALUE) params.append("dataset_id", datasetFilter);
      // No backend search for inference yet.

      try {
        const res = await apiService.get<PaginatedInferenceJobRead>(
          `/ml/infer?${params.toString()}`
        );
        setInferenceJobs(res.items || []);
        setInfPag(prev => ({ ...prev, totalItems: res.total || 0, isLoading: false }));
      } catch (err) {
        handleApiError(err, "Failed to fetch inference jobs");
        setInfErr(err instanceof Error ? err.message : "Error");
        setInfPag(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    },
    [statusFilter, datasetFilter]
  );

  /* ---------------- refetch on filters + first load ---------------- */
  useEffect(() => {
    if (activeTab === "training") fetchTraining(1);
    if (activeTab === "hpSearch") fetchHp(1);
    if (activeTab === "inference") fetchInf(1);
  }, [activeTab, debouncedSearch, statusFilter, datasetFilter]);

  /* ---------------- page-change effects ---------------- */
  useEffect(() => {
    fetchTraining(trainingPag.currentPage);
  }, [trainingPag.currentPage]);

  useEffect(() => {
    fetchHp(hpPag.currentPage);
  }, [hpPag.currentPage]);

  useEffect(() => {
    fetchInf(infPag.currentPage);
  }, [infPag.currentPage]);

  /* ---------------- cancel‑job dialog helpers ---------------- */
  const [jobToCancel, setJobToCancel] = useState<
    | { id: number | string; celeryTaskId: string | null; name: string }
    | null
  >(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const confirmCancelJob = (job: {
    id: string | number;
    celeryTaskId?: string | null;
    name: string;
  }) => {
    if (!job.celeryTaskId) {
      toast({
        variant: "destructive",
        title: "Cannot Cancel",
        description: "This job does not have an active task ID to revoke."
      });
      return;
    }
    setJobToCancel({
      id: job.id,
      celeryTaskId: job.celeryTaskId ?? null,
      name: job.name
    });
  };

  const executeCancelJob = async () => {
    if (!jobToCancel?.celeryTaskId) return;
    setIsCancelling(true);
    try {
      await apiService.post(`/tasks/${jobToCancel.celeryTaskId}/revoke`);
      toast({
        title: "Revocation Sent",
        description: `Attempting to revoke job: ${jobToCancel.name}`
      });
      setJobToCancel(null);
      setTimeout(() => {
        if (activeTab === "training") fetchTraining(trainingPag.currentPage);
        if (activeTab === "hpSearch") fetchHp(hpPag.currentPage);
      }, 2500);
    } catch (err) {
      handleApiError(err, "Failed to send revoke command");
    } finally {
      setIsCancelling(false);
    }
  };

  /* ---------------- helpers ---------------- */
  const formatDate = (d?: string | null) => (d ? new Date(d).toLocaleString() : "N/A");

  const getStatusBadge = (jobId: number, key: JobTypeKey, staticStatus?: any) => {
    const entityType =
      key === "training" ? "TrainingJob" : key === "hpSearch" ? "HPSearchJob" : "InferenceJob";
    const taskJobType = key === "training" ? "model_training" : key === "hpSearch" ? "hp_search" : undefined;
    const live = getLatestTaskForEntity(taskStatuses, entityType, jobId, taskJobType);

    const current = live || (staticStatus ? ({ status: staticStatus } as TaskStatusUpdatePayload) : undefined);
    if (!current?.status)
      return (
        <Badge variant="secondary" className="text-xs">
          Unknown
        </Badge>
      );

    let variant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon: React.ReactNode = null;
    let text = String(current.status_message || current.status);

    switch (String(current.status).toUpperCase()) {
      case JobStatusEnum.SUCCESS.toUpperCase():
        variant = "default";
        icon = <CheckCircle className="h-3 w-3 mr-1" />;
        text = "Success";
        break;
      case JobStatusEnum.RUNNING.toUpperCase():
      case JobStatusEnum.STARTED.toUpperCase():
        variant = "outline";
        icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />;
        text = `${text} (${current.progress ?? 0}%)`;
        break;
      case JobStatusEnum.PENDING.toUpperCase():
        variant = "outline";
        icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />;
        text = "Pending";
        break;
      case JobStatusEnum.FAILED.toUpperCase():
        variant = "destructive";
        icon = <AlertCircle className="h-3 w-3 mr-1" />;
        text = "Failed";
        break;
      case JobStatusEnum.REVOKED.toUpperCase():
        variant = "destructive";
        icon = <StopCircle className="h-3 w-3 mr-1" />;
        text = "Revoked";
        break;
      default:
        text = String(current.status).toUpperCase();
    }

    return (
      <Badge variant={variant} className="whitespace-nowrap text-xs px-1.5 py-0.5">
        {icon} {text}
      </Badge>
    );
  };

  /* ---------------- column definitions ---------------- */
  const trainingCols = [
    {
      header: "Job Name",
      accessor: (j: TrainingJobRead) => j.config.model_name,
      className: "font-medium break-all max-w-xs"
    },
    {
      header: "Dataset",
      accessor: (j: TrainingJobRead) => (
        <Link
          href={`/datasets/${j.dataset_id}`}
          className="hover:underline text-primary text-xs"
        >
          ID: {j.dataset_id}
        </Link>
      )
    },
    {
      header: "Model Type",
      accessor: (j: TrainingJobRead) => (
        <Badge variant="outline" className="text-xs">
          {j.config.model_type}
        </Badge>
      )
    },
    {
      header: "Status",
      accessor: (j: TrainingJobRead) => getStatusBadge(j.id, "training", j.status)
    },
    { header: "Started", accessor: (j: TrainingJobRead) => formatDate(j.started_at) },
    { header: "Completed", accessor: (j: TrainingJobRead) => formatDate(j.completed_at) }
  ];

  const hpCols = [
    {
      header: "Study Name",
      accessor: (j: HPSearchJobRead) => j.optuna_study_name,
      className: "font-medium break-all max-w-xs"
    },
    {
      header: "Dataset",
      accessor: (j: HPSearchJobRead) => (
        <Link
          href={`/datasets/${j.dataset_id}`}
          className="hover:underline text-primary text-xs"
        >
          ID: {j.dataset_id}
        </Link>
      )
    },
    {
      header: "Model Type",
      accessor: (j: HPSearchJobRead) => (
        <Badge variant="outline" className="text-xs">
          {j.config.model_type}
        </Badge>
      )
    },
    { header: "Status", accessor: (j: HPSearchJobRead) => getStatusBadge(j.id, "hpSearch", j.status) },
    { header: "Started", accessor: (j: HPSearchJobRead) => formatDate(j.started_at) },
    {
      header: "Trials",
      accessor: (j: HPSearchJobRead) =>
        j.best_trial_id !== null
          ? `${j.best_trial_id} / ${j.config.optuna_config.n_trials}`
          : `0 / ${j.config.optuna_config.n_trials}`
    }
  ];

  const infCols = [
    {
      header: "Commit Hash",
      accessor: (j: InferenceJobRead) => (
        <span
          className="font-mono text-xs"
          title={j.input_reference?.commit_hash}
        >
          {String(j.input_reference?.commit_hash).substring(0, 12) || "N/A"}…
        </span>
      )
    },
    {
      header: "Model Used",
      accessor: (j: InferenceJobRead) => (
        <Link
          href={`/models/${j.ml_model_id}`}
          className="hover:underline text-primary text-xs"
        >
          ID: {j.ml_model_id}
        </Link>
      )
    },
    {
      header: "Status",
      accessor: (j: InferenceJobRead) => getStatusBadge(j.id, "inference", j.status)
    },
    { header: "Triggered", accessor: (j: InferenceJobRead) => formatDate(j.created_at) },
    {
      header: "Result",
      accessor: (j: InferenceJobRead) =>
        j.prediction_result?.commit_prediction !== undefined ? (
          j.prediction_result.commit_prediction === 1 ? (
            <Badge variant="destructive">Defect</Badge>
          ) : (
            <Badge className="bg-green-600 hover:bg-green-700">Clean</Badge>
          )
        ) : (
          "N/A"
        )
    }
  ];

  /* ---------------- search placeholder ---------------- */
  const searchPlaceholder = useMemo(() => {
    switch (activeTab) {
      case "training":
        return "Search by job name…";
      case "hpSearch":
        return "Search by study name…";
      case "inference":
        return "Search by commit hash…";
      default:
        return "Search…";
    }
  }, [activeTab]);

  /* ---------------- onPageChange helpers (stable refs) ---------------- */
  const changeTrainingPage = (p: number) => setTrainingPag(prev => ({ ...prev, currentPage: p }));
  const changeHpPage = (p: number) => setHpPag(prev => ({ ...prev, currentPage: p }));
  const changeInfPage = (p: number) => setInfPag(prev => ({ ...prev, currentPage: p }));

  /* ---------------- JSX ---------------- */
  return (
    <MainLayout>
      <PageContainer
        title="ML Jobs Dashboard"
        description="Monitor and manage your model training, hyper‑parameter searches and inference tasks."
        actions={
          <div className="flex space-x-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/jobs/train">New Training</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/jobs/hp-search">New HP Search</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/jobs/inference">Run Inference</Link>
            </Button>
          </div>
        }
      >
        {/* ---------------- filters ---------------- */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Input
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
              {Object.values(JobStatusEnum).map(s => (
                <SelectItem key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={datasetFilter}
            onValueChange={setDatasetFilter}
            disabled={isLoadingDatasets}
          >
            <SelectTrigger>
              <SelectValue placeholder="All Datasets" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER_VALUE}>All Datasets</SelectItem>
              {datasets.map(ds => (
                <SelectItem key={ds.id} value={String(ds.id)}>
                  {ds.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* ---------------- tabs ---------------- */}
        <Tabs value={activeTab} onValueChange={(v: string) => setActiveTab(v as JobTypeKey)}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="training">
              Training {trainingPag.isLoading ? <Loader2 className="h-3 w-3 animate-spin ml-1" /> : `(${trainingPag.totalItems})`}
            </TabsTrigger>
            <TabsTrigger value="hpSearch">
              HP Search {hpPag.isLoading ? <Loader2 className="h-3 w-3 animate-spin ml-1" /> : `(${hpPag.totalItems})`}
            </TabsTrigger>
            <TabsTrigger value="inference">
              Inference {infPag.isLoading ? <Loader2 className="h-3 w-3 animate-spin ml-1" /> : `(${infPag.totalItems})`}
            </TabsTrigger>
          </TabsList>

          {/* ---------------- training tab ---------------- */}
          <TabsContent value="training">
            <Card>
              <CardHeader>
                <CardTitle>Training Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <JobTable
                  entityType="training"
                  columns={trainingCols}
                  data={trainingJobs}
                  isLoading={trainingPag.isLoading}
                  error={trainingErr}
                  paginationState={trainingPag}
                  onPageChange={changeTrainingPage}
                  onCancelJob={confirmCancelJob}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* ---------------- hp search tab ---------------- */}
          <TabsContent value="hpSearch">
            <Card>
              <CardHeader>
                <CardTitle>Hyper‑parameter Search Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <JobTable
                  entityType="hpSearch"
                  columns={hpCols}
                  data={hpSearchJobs}
                  isLoading={hpPag.isLoading}
                  error={hpErr}
                  paginationState={hpPag}
                  onPageChange={changeHpPage}
                  onCancelJob={confirmCancelJob}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* ---------------- inference tab ---------------- */}
          <TabsContent value="inference">
            <Card>
              <CardHeader>
                <CardTitle>Inference Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <JobTable
                  entityType="inference"
                  columns={infCols}
                  data={inferenceJobs}
                  isLoading={infPag.isLoading}
                  error={infErr}
                  paginationState={infPag}
                  onPageChange={changeInfPage}
                  onCancelJob={confirmCancelJob}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ---------------- cancel‑job dialog ---------------- */}
        <AlertDialog open={!!jobToCancel} onOpenChange={o => !o && setJobToCancel(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirm Cancel Job</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to attempt to cancel job: "{jobToCancel?.name}" (Task
                ID: {jobToCancel?.celeryTaskId})? This action may not be immediately
                effective if the task is already in a non‑interruptible state.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isCancelling}>
                Back
              </AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive hover:bg-destructive/90"
                onClick={executeCancelJob}
                disabled={isCancelling}
              >
                {isCancelling ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Cancelling…
                  </>
                ) : (
                  "Yes, Cancel Job"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </PageContainer>
    </MainLayout>
  );
}

/* -------------------------------------------------------------------------------------------------
 * Top‑level default export (with Suspense wrapper)
 * ------------------------------------------------------------------------------------------------*/
export default function JobsPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading jobs dashboard…" />}>
      <JobsPageContent />
    </Suspense>
  );
}
