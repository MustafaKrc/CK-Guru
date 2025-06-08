// frontend/app/repositories/[id]/commits/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiService, handleApiError } from '@/lib/apiService';
import { PaginatedCommitList, CommitListItem, Repository, TaskResponse } from '@/types/api';
import { CommitIngestionStatusEnum } from '@/types/api/enums';
import { useTaskStore } from '@/store/taskStore';
import { useToast } from '@/hooks/use-toast';

import { MainLayout } from '@/components/main-layout';
import { PageContainer } from '@/components/ui/page-container';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, GitCommit, CheckCircle, Loader2, AlertCircle, RefreshCw, Layers, Eye } from 'lucide-react';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { CommitDetailDialog } from '@/components/repositories/CommitDetailDialog';

const ITEMS_PER_PAGE = 20;

export default function RepositoryCommitsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const repoId = params.id;
  const { toast } = useToast();

  const [repo, setRepo] = useState<Repository | null>(null);
  const [commits, setCommits] = useState<CommitListItem[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [error, setError] = useState<string | null>(null);
  
  const [ingestingCommits, setIngestingCommits] = useState<Record<string, boolean>>({});
  const [selectedCommitDialog, setSelectedCommitDialog] = useState<string | null>(null);

  const { taskStatuses } = useTaskStore();

  const fetchCommits = useCallback(async (page: number) => {
    if (!repoId) return;
    setPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setError(null);
    try {
      const skip = (page - 1) * ITEMS_PER_PAGE;
      const response = await apiService.getCommits(repoId, { skip, limit: ITEMS_PER_PAGE });
      setCommits(response.items || []);
      setPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to load commits");
      setError(err instanceof Error ? err.message : "Could not load commit history.");
      setPagination(prev => ({ ...prev, isLoading: false }));
    }
  }, [repoId]);
  
  useEffect(() => {
    if (repoId) {
      apiService.get<Repository>(`/repositories/${repoId}`).then(setRepo).catch(() => setError("Failed to load repository name."));
      fetchCommits(1);
    }
  }, [repoId, fetchCommits]);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= Math.ceil(pagination.totalItems / ITEMS_PER_PAGE)) {
      fetchCommits(newPage);
    }
  };

  const handleIngest = async (commitHash: string) => {
    setIngestingCommits(prev => ({ ...prev, [commitHash]: true }));
    try {
        const response: TaskResponse = await apiService.triggerCommitIngestion(repoId, commitHash);
        toast({ title: "Ingestion Started", description: `Task ${response.task_id} has begun processing commit ${commitHash.substring(0,7)}.`});
        setCommits(currentCommits => currentCommits.map(c => 
            c.commit_hash === commitHash ? { ...c, ingestion_status: CommitIngestionStatusEnum.PENDING } : c
        ));
    } catch (error) {
        handleApiError(error, "Failed to start ingestion");
        setIngestingCommits(prev => ({ ...prev, [commitHash]: false }));
    }
  };
  
    const getStatusBadgeAndActions = (commit: CommitListItem) => {
        const liveTask = Object.values(taskStatuses).find(t => 
            t.entity_type === "CommitDetails" && t.status_message?.includes(commit.commit_hash)
        );

        const isLocallyLoading = ingestingCommits[commit.commit_hash];
        let effectiveStatus = commit.ingestion_status;
        if (liveTask && (liveTask.status === 'RUNNING' || liveTask.status === 'PENDING')) {
            effectiveStatus = liveTask.status as CommitIngestionStatusEnum;
        }

        const badge = (() => {
            switch (effectiveStatus.toUpperCase()) {
                case "COMPLETE": return <Badge variant="default" className="bg-green-600 hover:bg-green-700 text-xs"><CheckCircle className="h-3 w-3 mr-1"/>Complete</Badge>;
                case "RUNNING": case "PENDING": return <Badge variant="outline" className="text-blue-600 border-blue-600 text-xs"><Loader2 className="h-3 w-3 animate-spin mr-1"/>Processing</Badge>;
                case "FAILED": return <Badge variant="destructive" className="text-xs"><AlertCircle className="h-3 w-3 mr-1"/>Failed</Badge>;
                default: return <Badge variant="secondary" className="text-xs">Not Ingested</Badge>;
            }
        })();

        const actionButton = (() => {
            switch (effectiveStatus.toUpperCase()) {
                case "FAILED": return <Button variant="destructive" size="sm" onClick={() => handleIngest(commit.commit_hash)} disabled={isLocallyLoading}>{isLocallyLoading ? <Loader2 className="h-4 w-4 animate-spin"/> : <RefreshCw className="mr-2 h-4 w-4"/>}Re-Ingest</Button>;
                case "NOT_INGESTED": return <Button variant="default" size="sm" onClick={() => handleIngest(commit.commit_hash)} disabled={isLocallyLoading}>{isLocallyLoading ? <Loader2 className="h-4 w-4 animate-spin"/> : "Ingest"}</Button>;
                default: return null; // No primary action for complete/processing
            }
        })();

        return { badge, actionButton };
    };
    
  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

  return (
    <MainLayout>
      <PageContainer
        title={`Commit History: ${repo?.name || 'Loading...'}`}
        description="Browse the commit history. Select a commit to view details and run predictions."
        actions={<Button variant="outline" onClick={() => router.push(`/repositories/${repoId}`)}><ArrowLeft className="mr-2 h-4 w-4"/>Back to Repository</Button>}
      >
        <div className="rounded-md border">
          <Table>
            <TableHeader><TableRow><TableHead className="w-[100px]">Hash</TableHead><TableHead>Message & Author</TableHead><TableHead className="w-[180px]">Date</TableHead><TableHead className="w-[120px]">Status</TableHead><TableHead className="w-[150px] text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
                 {pagination.isLoading && commits.length === 0 ? (
                    Array.from({ length: 15 }).map((_, i) => <TableRow key={i}><TableCell colSpan={5}><Skeleton className="h-8 w-full"/></TableCell></TableRow>)
                 ) : (
                    commits.map(commit => {
                        const { badge, actionButton } = getStatusBadgeAndActions(commit);
                        return (
                        <TableRow key={commit.commit_hash}>
                            <TableCell>
                                <Link href={`/repositories/${repoId}/commits/${commit.commit_hash}`} className="font-mono text-sm text-primary hover:underline">
                                    {commit.commit_hash.substring(0, 7)}
                                </Link>
                            </TableCell>
                            <TableCell>
                                <p className="font-medium truncate max-w-lg">{commit.message_short}</p>
                                <p className="text-xs text-muted-foreground">{commit.author_name}</p>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">{formatDate(commit.author_date)}</TableCell>
                            <TableCell>{badge}</TableCell>
                            <TableCell className="text-right space-x-2">
                                <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setSelectedCommitDialog(commit.commit_hash);}}>
                                    <Eye className="mr-2 h-4 w-4"/>Quick Peek
                                </Button>
                                {actionButton}
                            </TableCell>
                        </TableRow>
                    )})
                 )}
            </TableBody>
          </Table>
        </div>
        <div className="mt-4"><Pagination><PaginationContent>
            <PaginationItem><PaginationPrevious onClick={() => handlePageChange(pagination.currentPage - 1)} aria-disabled={pagination.currentPage <= 1}/></PaginationItem>
            <PaginationItem><PaginationLink>{pagination.currentPage}</PaginationLink></PaginationItem>
            <PaginationItem><PaginationEllipsis /></PaginationItem>
            <PaginationItem><PaginationNext onClick={() => handlePageChange(pagination.currentPage + 1)} aria-disabled={pagination.currentPage >= Math.ceil(pagination.totalItems / ITEMS_PER_PAGE)}/></PaginationItem>
        </PaginationContent></Pagination></div>
        {repo && (<CommitDetailDialog repoId={repoId} commitHash={selectedCommitDialog} repoName={repo.name} onOpenChange={(isOpen) => !isOpen && setSelectedCommitDialog(null)} />)}
      </PageContainer>
    </MainLayout>
  );
}