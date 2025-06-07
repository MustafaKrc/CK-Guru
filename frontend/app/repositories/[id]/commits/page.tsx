"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiService, handleApiError } from '@/lib/apiService';
import { PaginatedCommitList, CommitListItem, Repository } from '@/types/api';
import { CommitIngestionStatusEnum } from '@/types/api/enums';

import { MainLayout } from '@/components/main-layout';
import { PageContainer } from '@/components/ui/page-container';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, GitCommit, CheckCircle, Loader2, AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";

const ITEMS_PER_PAGE = 20;

export default function RepositoryCommitsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const repoId = params.id;

  const [repo, setRepo] = useState<Repository | null>(null);
  const [commits, setCommits] = useState<CommitListItem[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [error, setError] = useState<string | null>(null);

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
    if (newPage !== pagination.currentPage) {
      fetchCommits(newPage);
    }
  };

  const getStatusBadge = (status: CommitIngestionStatusEnum) => {
    switch (status) {
      case CommitIngestionStatusEnum.COMPLETE:
        return <Badge variant="default" className="bg-green-600 hover:bg-green-700 text-xs">Complete</Badge>;
      case CommitIngestionStatusEnum.RUNNING:
        return <Badge variant="outline" className="text-blue-600 border-blue-600 text-xs"><Loader2 className="h-3 w-3 animate-spin mr-1"/>Running</Badge>;
      case CommitIngestionStatusEnum.PENDING:
        return <Badge variant="outline" className="text-yellow-600 border-yellow-600 text-xs"><Loader2 className="h-3 w-3 animate-spin mr-1"/>Pending</Badge>;
      case CommitIngestionStatusEnum.FAILED:
        return <Badge variant="destructive" className="text-xs">Failed</Badge>;
      case CommitIngestionStatusEnum.NOT_INGESTED:
        return <Badge variant="secondary" className="text-xs">Not Ingested</Badge>;
      default:
        return <Badge variant="secondary" className="text-xs">Unknown</Badge>;
    }
  };
  
  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

  const renderContent = () => {
    if (pagination.isLoading && commits.length === 0) {
      return Array.from({ length: ITEMS_PER_PAGE }).map((_, index) => (
        <TableRow key={`skel-commit-${index}`}>
          <TableCell><Skeleton className="h-5 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-full" /></TableCell>
          <TableCell><Skeleton className="h-5 w-32" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
        </TableRow>
      ));
    }

    if (error) return <TableRow><TableCell colSpan={4} className="text-center py-6 text-destructive">{error}</TableCell></TableRow>;
    if (commits.length === 0) return <TableRow><TableCell colSpan={4} className="text-center py-6 text-muted-foreground">No commits found for this repository. Ingest the repository to see commit history.</TableCell></TableRow>;

    return commits.map((commit) => (
      <TableRow key={commit.commit_hash}>
        <TableCell>
          <Link href={`/repositories/${repoId}/commits/${commit.commit_hash}`} className="font-mono text-sm text-primary hover:underline">
            {commit.commit_hash.substring(0, 7)}
          </Link>
        </TableCell>
        <TableCell>
          <p className="font-medium truncate max-w-md">{commit.message_short}</p>
          <p className="text-xs text-muted-foreground">{commit.author_name}</p>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">{formatDate(commit.author_date)}</TableCell>
        <TableCell>{getStatusBadge(commit.ingestion_status)}</TableCell>
      </TableRow>
    ));
  };
  
  return (
    <MainLayout>
      <PageContainer
        title={`Commit History: ${repo?.name || 'Loading...'}`}
        description="Browse the commit history. Select a commit to view details and run predictions."
        actions={<Button variant="outline" onClick={() => router.push(`/repositories/${repoId}`)}><ArrowLeft className="mr-2 h-4 w-4"/>Back to Repository</Button>}
      >
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Hash</TableHead>
                <TableHead>Message & Author</TableHead>
                <TableHead className="w-[180px]">Date</TableHead>
                <TableHead className="w-[120px]">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderContent()}</TableBody>
          </Table>
        </div>
        {/* Pagination Controls */}
      </PageContainer>
    </MainLayout>
  );
}