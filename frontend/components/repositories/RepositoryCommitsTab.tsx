// frontend/components/repositories/RepositoryCommitsTab.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiService, handleApiError } from "@/lib/apiService";
import { CommitListItem, TaskResponse } from "@/types/api";
import { CommitIngestionStatusEnum } from "@/types/api/enums";
import { useTaskStore } from "@/store/taskStore";
import { useToast } from "@/hooks/use-toast";

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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle, Loader2, RefreshCw, Eye, AlertCircle } from "lucide-react";
import { CommitDetailDialog } from "./CommitDetailDialog";

const ITEMS_PER_PAGE_PREVIEW = 10;

interface RepositoryCommitsTabProps {
  repoId: string;
  repoName: string;
}

export const RepositoryCommitsTab: React.FC<RepositoryCommitsTabProps> = ({ repoId, repoName }) => {
  const { toast } = useToast();
  const [commits, setCommits] = useState<CommitListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [ingestingCommits, setIngestingCommits] = useState<Record<string, boolean>>({});
  const [selectedCommitDialog, setSelectedCommitDialog] = useState<string | null>(null);

  const { taskStatuses } = useTaskStore();

  const fetchRecentCommits = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiService.getCommits(repoId, { limit: ITEMS_PER_PAGE_PREVIEW });
      setCommits(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load recent commits");
    } finally {
      setIsLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchRecentCommits();
  }, [fetchRecentCommits]);

  const handleIngest = async (commitHash: string) => {
    setIngestingCommits((prev) => ({ ...prev, [commitHash]: true }));
    try {
      const response: TaskResponse = await apiService.triggerCommitIngestion(repoId, commitHash);
      toast({
        title: "Ingestion Started",
        description: `Task ${response.task_id} is processing commit ${commitHash.substring(0, 7)}.`,
      });
      setCommits((currentCommits) =>
        currentCommits.map((c) =>
          c.commit_hash === commitHash
            ? { ...c, ingestion_status: CommitIngestionStatusEnum.PENDING }
            : c
        )
      );
    } catch (error) {
      handleApiError(error, "Failed to start ingestion");
      setIngestingCommits((prev) => ({ ...prev, [commitHash]: false }));
    }
  };

  const getStatusAndActions = (commit: CommitListItem) => {
    const liveTask = Object.values(taskStatuses).find(
      (t) => t.entity_type === "CommitDetails" && t.status_message?.includes(commit.commit_hash)
    );

    const isLocallyLoading = ingestingCommits[commit.commit_hash];
    let effectiveStatus = commit.ingestion_status;
    if (liveTask && (liveTask.status === "RUNNING" || liveTask.status === "PENDING")) {
      effectiveStatus = liveTask.status as CommitIngestionStatusEnum;
    }

    const badge = (() => {
      switch (effectiveStatus.toUpperCase()) {
        case "COMPLETE":
          return (
            <Badge variant="default" className="bg-green-600 hover:bg-green-700 text-xs">
              <CheckCircle className="h-3 w-3 mr-1" />
              Complete
            </Badge>
          );
        case "RUNNING":
        case "PENDING":
          return (
            <Badge variant="outline" className="text-blue-600 border-blue-600 text-xs">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Processing
            </Badge>
          );
        case "FAILED":
          return (
            <Badge variant="destructive" className="text-xs">
              <AlertCircle className="h-3 w-3 mr-1" />
              Failed
            </Badge>
          );
        default:
          return (
            <Badge variant="secondary" className="text-xs">
              Not Ingested
            </Badge>
          );
      }
    })();

    const actionButton = (() => {
      switch (effectiveStatus.toUpperCase()) {
        case "FAILED":
          return (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleIngest(commit.commit_hash)}
              disabled={isLocallyLoading}
            >
              {isLocallyLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Re-Ingest
            </Button>
          );
        case "NOT_INGESTED":
          return (
            <Button
              variant="default"
              size="sm"
              onClick={() => handleIngest(commit.commit_hash)}
              disabled={isLocallyLoading}
            >
              {isLocallyLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Ingest"}
            </Button>
          );
        default:
          return null;
      }
    })();

    return { badge, actionButton };
  };

  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Recent Commits</CardTitle>
          <CardDescription>
            A preview of the {ITEMS_PER_PAGE_PREVIEW} most recent commits. Click a hash to see the
            full page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Hash</TableHead>
                  <TableHead>Message & Author</TableHead>
                  <TableHead className="w-[180px]">Date</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[200px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={5}>
                        <Skeleton className="h-8 w-full" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : commits.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No commits found.
                    </TableCell>
                  </TableRow>
                ) : (
                  commits.map((commit) => {
                    const { badge, actionButton } = getStatusAndActions(commit);
                    return (
                      <TableRow key={commit.commit_hash}>
                        <TableCell>
                          <Link
                            href={`/repositories/${repoId}/commits/${commit.commit_hash}`}
                            className="font-mono text-sm text-primary hover:underline"
                          >
                            {commit.commit_hash.substring(0, 7)}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <p className="font-medium truncate max-w-md">{commit.message_short}</p>
                          <p className="text-xs text-muted-foreground">{commit.author_name}</p>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(commit.author_date)}
                        </TableCell>
                        <TableCell>{badge}</TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedCommitDialog(commit.commit_hash)}
                          >
                            <Eye className="mr-2 h-4 w-4" />
                            Quick Peek
                          </Button>
                          {actionButton}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
        <CardFooter>
          <Button asChild className="w-full">
            <Link href={`/repositories/${repoId}/commits`}>View All Commits</Link>
          </Button>
        </CardFooter>
      </Card>
      {repoName && (
        <CommitDetailDialog
          repoId={repoId}
          commitHash={selectedCommitDialog}
          repoName={repoName}
          onOpenChange={(isOpen) => !isOpen && setSelectedCommitDialog(null)}
        />
      )}
    </>
  );
};
