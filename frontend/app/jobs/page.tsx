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

import { MainLayout } from "@/components/main-layout";
import { PageLoader } from "@/components/ui/page-loader";
import {
  AlertCircle,
  ArrowUpDown,
  CheckCircle,
  Eye,
  Loader2,
  MoreHorizontal,
  Plus,
  Puzzle,
  RefreshCw,
  StopCircle,
  Wand2,
  Play,
} from "lucide-react";
import { apiService, handleApiError } from "@/lib/apiService";
import { useDebounce } from "@/hooks/useDebounce";
import { toast } from "@/components/ui/use-toast";
import { useTaskStore } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import {
  HPSearchJobRead,
  PaginatedHPSearchJobRead,
  InferenceJobRead,
  PaginatedInferenceJobRead,
  TrainingJobRead,
  PaginatedTrainingJobRead,
  Repository,
  PaginatedRepositoryRead,
  JobStatusEnum,
} from "@/types/api";

import { TaskStatusUpdatePayload } from "@/store/taskStore";

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
import { generatePagination } from "@/lib/paginationUtils";
import { SearchableSelect, SearchableSelectOption } from '@/components/ui/searchable-select';
import { Label } from "@/components/ui/label";

const ALL_FILTER_VALUE = "_all_";
type JobTypeKey = "training" | "hpSearch" | "inference";
type SortableKeys = "name" | "status" | "created_at" | 'repository_name' | 'dataset_name' | 'model_type';
type SortConfig = { key: SortableKeys; direction: "asc" | "desc" };
type JobPaginationState = { currentPage: number; totalItems: number; isLoading: boolean, itemsPerPage: number };

const SortableHeader: React.FC<{
  sortKey: SortableKeys;
  sortConfig: SortConfig;
  onSort: (key: SortableKeys) => void;
  children: React.ReactNode;
  className?: string;
}> = ({ sortKey, sortConfig, onSort, children, className }) => (
    <Button variant="ghost" onClick={() => onSort(sortKey)} className={className}>
        {children}
        <ArrowUpDown className={`ml-2 h-4 w-4 transition-opacity ${sortConfig.key === sortKey ? 'opacity-100' : 'opacity-30'}`} />
    </Button>
);

function JobsPageContent() {
  const searchParamsHook = useSearchParams();
  const initialTab = (searchParamsHook.get("tab") as JobTypeKey) || "training";
  const [activeTab, setActiveTab] = useState<JobTypeKey>(initialTab);

  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);

  const [trainingPag, setTrainingPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true, itemsPerPage: 10 });
  const [hpPag, setHpPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true, itemsPerPage: 10 });
  const [infPag, setInfPag] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true, itemsPerPage: 10 });

  const [trainingErr, setTrainingErr] = useState<string | null>(null);
  const [hpErr, setHpErr] = useState<string | null>(null);
  const [infErr, setInfErr] = useState<string | null>(null);
  
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 200);
  const [statusFilter, setStatusFilter] = useState<string>(ALL_FILTER_VALUE);
  const [repositoryFilter, setRepositoryFilter] = useState<string>(ALL_FILTER_VALUE);

  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: "created_at", direction: "desc" });

  const { taskStatuses } = useTaskStore();

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  const currentPaginationState = useMemo(() => {
    if (activeTab === 'training') return trainingPag;
    if (activeTab === 'hpSearch') return hpPag;
    return infPag;
  }, [activeTab, trainingPag, hpPag, infPag]);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiService.get<PaginatedRepositoryRead>("/repositories?limit=500");
        setRepositories(res.items || []);
      } catch (err) {
        handleApiError(err, "Failed to fetch repositories");
      } finally {
        setIsLoadingRepositories(false);
      }
    })();
  }, []);

  const fetchJobs = useCallback(async (jobTypeToFetch: JobTypeKey) => {
    let fetcher: any;
    let setItems: React.Dispatch<React.SetStateAction<any[]>>;
    let setPag: React.Dispatch<React.SetStateAction<JobPaginationState>>;
    let setErr: React.Dispatch<React.SetStateAction<string | null>>;
    let pagState: JobPaginationState;

    if (jobTypeToFetch === "training") {
      fetcher = apiService.getTrainingJobs;
      setItems = setTrainingJobs as React.Dispatch<React.SetStateAction<any[]>>;
      setPag = setTrainingPag;
      setErr = setTrainingErr;
      pagState = trainingPag;
    } else if (jobTypeToFetch === "hpSearch") {
      fetcher = apiService.getHpSearchJobs;
      setItems = setHpSearchJobs as React.Dispatch<React.SetStateAction<any[]>>;
      setPag = setHpPag;
      setErr = setHpErr;
      pagState = hpPag;
    } else if (jobTypeToFetch === "inference") {
      fetcher = apiService.getInferenceJobs;
      setItems = setInferenceJobs as React.Dispatch<React.SetStateAction<any[]>>;
      setPag = setInfPag;
      setErr = setInfErr;
      pagState = infPag;
    } else {
      return;
    }

    setPag(prev => ({ ...prev, isLoading: true }));
    setErr(null);

    const params = {
      skip: (pagState.currentPage - 1) * pagState.itemsPerPage,
      limit: pagState.itemsPerPage,
      ...(debouncedSearch && { nameFilter: debouncedSearch }),
      ...(statusFilter !== ALL_FILTER_VALUE && { status: statusFilter }),
      ...(repositoryFilter !== ALL_FILTER_VALUE && { repository_id: parseInt(repositoryFilter) }),
      sortBy: sortConfig.key,
      sortDir: sortConfig.direction,
    };

    try {
      const res = await fetcher(params as any);
      setItems(res.items || []);
      setPag(prev => ({ ...prev, totalItems: res.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, `Failed to fetch ${jobTypeToFetch} jobs`);
      setErr(err instanceof Error ? err.message : "Error fetching data.");
      setPag(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [
    trainingPag, hpPag, infPag, // Depend on all pagination states
    debouncedSearch, statusFilter, repositoryFilter, sortConfig,
    // Setters are stable, no need to list them explicitly unless ESLint complains
    // setTrainingJobs, setHpSearchJobs, setInferenceJobs,
    // setTrainingPag, setHpPag, setInfPag,
    // setTrainingErr, setHpErr, setInfErr
  ]);

  useEffect(() => {
    // Initial load for all tabs
    const performInitialLoad = async () => {
      await Promise.all([
        fetchJobs("training"),
        fetchJobs("hpSearch"),
        fetchJobs("inference")
      ]);
      setInitialLoadComplete(true);
    };
    performInitialLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount, fetchJobs is captured

  useEffect(() => {
    // Subsequent fetches for the active tab
    if (!initialLoadComplete) {
      return; // Don't fetch if initial multi-load isn't complete
    }
    fetchJobs(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeTab,
    debouncedSearch,
    statusFilter,
    repositoryFilter,
    sortConfig,
    currentPaginationState.currentPage,
    currentPaginationState.itemsPerPage,
    initialLoadComplete
    // fetchJobs is deliberately omitted here to prevent infinite loops.
    // The fetchJobs function is always up-to-date due to its own useCallback
    // and will use the latest state when called by this effect.
  ]);


  useEffect(() => {
    setSortConfig({ key: 'created_at', direction: 'desc' });
  }, [activeTab]);


  const handleSort = (key: SortableKeys) => {
    setSortConfig(prev => ({ key, direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc' }));
  };
  
  const handlePageChange = (page: number) => {
    if (activeTab === 'training') setTrainingPag(p => ({ ...p, currentPage: page }));
    if (activeTab === 'hpSearch') setHpPag(p => ({ ...p, currentPage: page }));
    if (activeTab === 'inference') setInfPag(p => ({ ...p, currentPage: page }));
  };

  const handleItemsPerPageChange = (value: string) => {
    const newSize = parseInt(value, 10);
    if (activeTab === 'training') setTrainingPag(p => ({ ...p, itemsPerPage: newSize, currentPage: 1 }));
    if (activeTab === 'hpSearch') setHpPag(p => ({ ...p, itemsPerPage: newSize, currentPage: 1 }));
    if (activeTab === 'inference') setInfPag(p => ({ ...p, itemsPerPage: newSize, currentPage: 1 }));
  };

  

  const formatDate = (d?: string | null) => (d ? new Date(d).toLocaleString() : "N/A");

  const getStatusBadge = (jobId: number, key: JobTypeKey, staticStatus?: any) => {
    const entityType = key === "training" ? "TrainingJob" : key === "hpSearch" ? "HPSearchJob" : "InferenceJob";
    const taskJobType = key === "training" ? "model_training" : key === "hpSearch" ? "hp_search" : undefined;
    const live = getLatestTaskForEntity(taskStatuses, entityType, jobId, taskJobType);

    const current = live || (staticStatus ? ({ status: staticStatus } as TaskStatusUpdatePayload) : undefined);
    if (!current?.status) return <Badge variant="secondary" className="text-xs">Unknown</Badge>;

    let variant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon: React.ReactNode = null;
    let text = String(current.status_message || current.status);

    switch (String(current.status).toUpperCase()) {
      case JobStatusEnum.SUCCESS.toUpperCase(): variant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = "Success"; break;
      case JobStatusEnum.RUNNING.toUpperCase(): case JobStatusEnum.STARTED.toUpperCase(): variant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `${text} (${current.progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING.toUpperCase(): variant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; text = "Pending"; break;
      case JobStatusEnum.FAILED.toUpperCase(): variant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = "Failed"; break;
      case JobStatusEnum.REVOKED.toUpperCase(): variant = "destructive"; icon = <StopCircle className="h-3 w-3 mr-1" />; text = "Revoked"; break;
      default: text = String(current.status).toUpperCase();
    }
    return <Badge variant={variant} className="whitespace-nowrap text-xs px-1.5 py-0.5">{icon} {text}</Badge>;
  };
  
  const repositoryOptions: SearchableSelectOption[] = useMemo(() => ([
    { value: ALL_FILTER_VALUE, label: 'All Repositories' },
    ...repositories.map(r => ({ value: r.id.toString(), label: r.name }))
  ]), [repositories]);

  const searchPlaceholder = useMemo(() => {
    switch (activeTab) {
      case "training": return "Search by job name...";
      case "hpSearch": return "Search by study name...";
      case "inference": return "Search by commit hash...";
      default: return "Search...";
    }
  }, [activeTab]);

  const renderJobTable = <T extends TrainingJobRead | HPSearchJobRead | InferenceJobRead>(
    title: string,
    data: T[],
    columns: { header: React.ReactNode; accessor: (job: T) => React.ReactNode; className?: string }[],
    paginationState: JobPaginationState,
    error: string | null
  ) => (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {paginationState.isLoading && data.length === 0 ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : error ? (
          <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>
        ) : data.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">No jobs found matching your criteria.</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader><TableRow>{columns.map((c, i) => <TableHead key={i}>{c.header}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {data.map((job: T) => ( // Consider using T here instead of any if possible
                  <TableRow key={job.id}>
                    {columns.map((c, i) => <TableCell key={i} className={`text-xs ${c.className || ''}`}>{c.accessor(job)}</TableCell>)}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        <PaginationControls paginationState={paginationState} onPageChange={handlePageChange} />
      </CardContent>
    </Card>
  );

  const PaginationControls: React.FC<{paginationState: JobPaginationState, onPageChange: (page: number) => void}> = ({ paginationState, onPageChange }) => {
    const totalPages = Math.ceil(paginationState.totalItems / paginationState.itemsPerPage);
    if (totalPages <= 1 && !paginationState.isLoading) return null; // Also hide if not loading and only 1 page
    const pages = generatePagination(paginationState.currentPage, totalPages);
    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem><PaginationPrevious onClick={() => onPageChange(paginationState.currentPage - 1)} aria-disabled={paginationState.currentPage <= 1 || paginationState.isLoading} className={(paginationState.currentPage <= 1 || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          {pages.map((p, i) => (
            <PaginationItem key={i}>
              {typeof p === 'number' ? <PaginationLink isActive={p === paginationState.currentPage} onClick={() => onPageChange(p)}>{p}</PaginationLink> : <PaginationEllipsis />}
            </PaginationItem>
          ))}
          <PaginationItem><PaginationNext onClick={() => onPageChange(paginationState.currentPage + 1)} aria-disabled={paginationState.currentPage >= totalPages || paginationState.isLoading} className={(paginationState.currentPage >= totalPages || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const trainingCols = [
    { header: <SortableHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>Model</SortableHeader>, accessor: (j: TrainingJobRead) => (j.id ? <Link href={`/jobs/${j.id}?type=training`} className="hover:underline text-primary"> {j.config.model_name}</Link> : j.id), className: "font-medium" },
    { header: <SortableHeader sortKey="repository_name" sortConfig={sortConfig} onSort={handleSort}>Repository</SortableHeader>, accessor: (j: TrainingJobRead) => (j.dataset?.repository ? <Link href={`/repositories/${j.dataset.repository.id}`} className="hover:underline text-primary">{j.dataset.repository.name}</Link> : `Repo ID: ${j.dataset?.repository_id || 'N/A'}`)},
    { header: <SortableHeader sortKey="dataset_name" sortConfig={sortConfig} onSort={handleSort}>Dataset</SortableHeader>, accessor: (j: TrainingJobRead) => (j.dataset ? <Link href={`/datasets/${j.dataset.id}`} className="hover:underline text-primary">{j.dataset.name}</Link> : `Dataset ID: ${j.dataset_id}`)},
    { header: <SortableHeader sortKey="model_type" sortConfig={sortConfig} onSort={handleSort}>Model Type</SortableHeader>, accessor: (j: TrainingJobRead) => <Badge variant="outline" className="text-xs">{j.config.model_type}</Badge>},
    { header: <SortableHeader sortKey="status" sortConfig={sortConfig} onSort={handleSort}>Status</SortableHeader>, accessor: (j: TrainingJobRead) => getStatusBadge(j.id, "training", j.status) },
    { header: <SortableHeader sortKey="created_at" sortConfig={sortConfig} onSort={handleSort}>Created</SortableHeader>, accessor: (j: TrainingJobRead) => formatDate(j.created_at) },
  ];

  const hpCols = [
    { header: <SortableHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>Study Name</SortableHeader>, accessor: (j: HPSearchJobRead) => (j.id ? <Link href={`/jobs/${j.id}?type=hp_search`} className="hover:underline text-primary"> {j.optuna_study_name}</Link> : j.id), className: "font-medium" },
    { header: <SortableHeader sortKey="repository_name" sortConfig={sortConfig} onSort={handleSort}>Repository</SortableHeader>, accessor: (j: HPSearchJobRead) => (j.dataset?.repository ? <Link href={`/repositories/${j.dataset.repository.id}`} className="hover:underline text-primary">{j.dataset.repository.name}</Link> : `Repo ID: ${j.dataset?.repository_id || 'N/A'}`)},
    { header: <SortableHeader sortKey="dataset_name" sortConfig={sortConfig} onSort={handleSort}>Dataset</SortableHeader>, accessor: (j: HPSearchJobRead) => (j.dataset ? <Link href={`/datasets/${j.dataset.id}`} className="hover:underline text-primary">{j.dataset.name}</Link> : `Dataset ID: ${j.dataset_id}`)},
    { header: <SortableHeader sortKey="model_type" sortConfig={sortConfig} onSort={handleSort}>Model Type</SortableHeader>, accessor: (j: HPSearchJobRead) => <Badge variant="outline" className="text-xs">{j.config.model_type}</Badge>},
    { header: <SortableHeader sortKey="status" sortConfig={sortConfig} onSort={handleSort}>Status</SortableHeader>, accessor: (j: HPSearchJobRead) => getStatusBadge(j.id, "hpSearch", j.status) },
    { header: <SortableHeader sortKey="created_at" sortConfig={sortConfig} onSort={handleSort}>Created</SortableHeader>, accessor: (j: HPSearchJobRead) => formatDate(j.created_at) },
  ];

  const infCols = [
    { header: "Commit Hash", accessor: (j: InferenceJobRead) => (j.input_reference?.commit_hash ? <Link href={`/repositories/${j.ml_model?.dataset?.repository?.id}/commits/${j.input_reference.commit_hash}`} className="hover:underline text-primary font-mono text-xs" title={j.input_reference.commit_hash}>{j.input_reference.commit_hash.substring(0, 12)}...</Link> : <span className="font-mono text-xs">N/A</span>)},
    { header: <SortableHeader sortKey="repository_name" sortConfig={sortConfig} onSort={handleSort}>Repository</SortableHeader>, accessor: (j: InferenceJobRead) => (j.ml_model?.dataset?.repository ? <Link href={`/repositories/${j.ml_model.dataset.repository.id}`} className="hover:underline text-primary">{j.ml_model.dataset.repository.name}</Link> : `Repo ID: ${j.ml_model?.dataset?.repository_id || 'N/A'}`)},
    { header: <SortableHeader sortKey="dataset_name" sortConfig={sortConfig} onSort={handleSort}>Dataset</SortableHeader>, accessor: (j: InferenceJobRead) => (j.ml_model?.dataset ? <Link href={`/datasets/${j.ml_model.dataset.id}`} className="hover:underline text-primary">{j.ml_model.dataset.name}</Link> : `Dataset ID: ${j.ml_model?.dataset?.id || 'N/A'}`)},
    { header: <SortableHeader sortKey="model_type" sortConfig={sortConfig} onSort={handleSort}>Model Type</SortableHeader>, accessor: (j: InferenceJobRead) => <Badge variant="outline" className="text-xs">{j.ml_model?.model_type}</Badge>},
    { header: <SortableHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>Model Name</SortableHeader>, accessor: (j: InferenceJobRead) => j.ml_model?.name || "N/A", className: "font-medium" },
    { header: <SortableHeader sortKey="status" sortConfig={sortConfig} onSort={handleSort}>Status</SortableHeader>, accessor: (j: InferenceJobRead) => getStatusBadge(j.id, "inference", j.status) },
    { header: <SortableHeader sortKey="created_at" sortConfig={sortConfig} onSort={handleSort}>Triggered</SortableHeader>, accessor: (j: InferenceJobRead) => formatDate(j.created_at) },
  ];

  return (
    <MainLayout>
      <PageContainer
        title="ML Jobs Dashboard"
        description="Monitor and manage your model training, hyperparameter searches and inference tasks."
        actions={
          <div className="flex space-x-2">
            <Button variant="outline" size="sm" asChild><Link href="/jobs/train">New Training</Link></Button>
            <Button variant="outline" size="sm" asChild><Link href="/jobs/hp-search">New HP Search</Link></Button>
            <Button size="sm" asChild><Link href="/jobs/inference">Run Inference</Link></Button>
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <Input placeholder={searchPlaceholder} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
              {Object.values(JobStatusEnum).map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
            </SelectContent>
          </Select>
          <SearchableSelect
            options={repositoryOptions}
            value={repositoryFilter}
            onValueChange={setRepositoryFilter}
            placeholder="Filter by Repository"
            searchPlaceholder="Search repositories..."
            emptyMessage="No repositories found."
            disabled={isLoadingRepositories}
            isLoading={isLoadingRepositories}
          />
           <div className="flex items-center gap-2">
            <Label htmlFor="items-per-page-jobs" className="text-sm shrink-0">Show:</Label>
            <Select value={String(currentPaginationState.itemsPerPage)} onValueChange={handleItemsPerPageChange}>
              <SelectTrigger id="items-per-page-jobs" className="w-full md:w-[80px]"><SelectValue /></SelectTrigger>
              <SelectContent>{[10, 25, 50].map(size => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as JobTypeKey)}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="training">Training ({trainingPag.totalItems})</TabsTrigger>
            <TabsTrigger value="hpSearch">HP Search ({hpPag.totalItems})</TabsTrigger>
            <TabsTrigger value="inference">Inference ({infPag.totalItems})</TabsTrigger>
          </TabsList>

          <TabsContent value="training" className="mt-4">{renderJobTable("Training Jobs", trainingJobs, trainingCols, trainingPag, trainingErr)}</TabsContent>
          <TabsContent value="hpSearch" className="mt-4">{renderJobTable("Hyperparameter Search Jobs", hpSearchJobs, hpCols, hpPag, hpErr)}</TabsContent>
          <TabsContent value="inference" className="mt-4">{renderJobTable("Inference Jobs", inferenceJobs, infCols, infPag, infErr)}</TabsContent>
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading jobs dashboard..." />}>
      <JobsPageContent />
    </Suspense>
  );
}