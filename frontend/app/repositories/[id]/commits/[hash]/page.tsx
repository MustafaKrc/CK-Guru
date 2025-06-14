"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

import { apiService, handleApiError } from '@/lib/apiService';
import { CommitPageResponse, Repository } from '@/types/api';
import { CommitIngestionStatusEnum, JobStatusEnum } from '@/types/api/enums';
import { useTaskStore } from '@/store/taskStore';
import { getLatestTaskForEntity } from '@/lib/taskUtils';

import { MainLayout } from '@/components/main-layout';
import { PageContainer } from '@/components/ui/page-container';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ArrowLeft, GitCommit, User, Calendar, FileText, Check, Plus, AlertCircle, RefreshCw, Loader2, Play, Eye, Lightbulb, MessageSquare } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { FileDiffViewer } from '@/components/commits/FileDiffViewer';
import { Label } from '@/components/ui/label';

const formatDate = (isoString?: string | null) => {
  if (!isoString) return "N/A";
  return new Date(isoString).toLocaleString();
};

function CommitDetailPage() {
  const params = useParams<{ id: string; hash: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const repoId = params.id;
  const commitHash = params.hash;

  const [commitData, setCommitData] = useState<CommitPageResponse | null>(null);
  const [repository, setRepository] = useState<Repository | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { taskStatuses } = useTaskStore();
  const liveTaskStatus = getLatestTaskForEntity(taskStatuses, "CommitDetails", commitData?.details?.id || 0, "feature_extraction");

  const fetchData = useCallback(async (showLoadingToast = false) => {
    if (!repoId || !commitHash) return;
    if(showLoadingToast) toast({ title: "Refreshing commit data...", description: "Please wait..." });
    
    setIsLoading(true);
    setError(null);
    try {
      const [commitResponse, repoResponse] = await Promise.all([
        apiService.getCommitDetails(repoId, commitHash),
        apiService.get<Repository>(`/repositories/${repoId}`)
      ]);
      
      setCommitData(commitResponse);
      setRepository(repoResponse);

      if(showLoadingToast) toast({ title: "Success", description: "Data refreshed!" });
    } catch (err) {
      handleApiError(err, "Failed to load page data");
      setError(err instanceof Error ? err.message : "Could not load data.");
    } finally {
      setIsLoading(false);
    }
  }, [repoId, commitHash, toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  useEffect(() => {
    const staticStatus = commitData?.ingestion_status;
    const liveStatus = liveTaskStatus?.status?.toUpperCase();

    if (liveStatus && (liveStatus === 'SUCCESS' || liveStatus === 'FAILED')) {
      if(staticStatus !== CommitIngestionStatusEnum.COMPLETE && staticStatus !== CommitIngestionStatusEnum.FAILED) {
        toast({ title: "Info", description: "Ingestion process finished. Refreshing details..." });
        setTimeout(() => fetchData(true), 1000);
      }
    }
  }, [liveTaskStatus, commitData, fetchData]);

  const handleIngestClick = async () => {
    setIsLoading(true);
    try {
      const taskResponse = await apiService.triggerCommitIngestion(repoId, commitHash);
      toast({
        title: "Ingestion Started",
        description: `Task ${taskResponse.task_id} has been queued to ingest commit details.`,
      });
      fetchData();
    } catch (err) {
      handleApiError(err, "Failed to start ingestion");
      setIsLoading(false);
    }
  };

  const renderStatus = () => {
    const status = liveTaskStatus?.status || commitData?.ingestion_status;
    const message = liveTaskStatus?.status_message || "Processing commit data...";
    const progress = liveTaskStatus?.progress;
    
    switch (status) {
      case CommitIngestionStatusEnum.NOT_INGESTED:
        return (
          <Card className="text-center py-10">
            <CardContent>
              <GitCommit className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-medium">Commit Not Ingested</h3>
              <p className="mt-1 text-sm text-muted-foreground">Details and metrics for this commit have not been processed yet.</p>
              <Button onClick={handleIngestClick} disabled={isLoading} className="mt-4">
                {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Ingest Commit Details
              </Button>
            </CardContent>
          </Card>
        );

      case CommitIngestionStatusEnum.PENDING:
      case CommitIngestionStatusEnum.RUNNING:
        return (
          <Card className="text-center py-10">
            <CardContent className="flex flex-col items-center">
              <Loader2 className="h-12 w-12 text-primary animate-spin" />
              <h3 className="mt-4 text-lg font-medium">Ingestion in Progress...</h3>
              <p className="mt-1 text-sm text-muted-foreground">{message} ({progress ?? 0}%)</p>
              <p className="text-xs text-muted-foreground mt-2">Task ID: {liveTaskStatus?.task_id || commitData?.celery_ingestion_task_id || 'N/A'}</p>
            </CardContent>
          </Card>
        );

      case CommitIngestionStatusEnum.FAILED:
        return (
           <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Ingestion Failed</AlertTitle>
            <AlertDescription>{commitData?.details?.message || "An error occurred during ingestion."}</AlertDescription>
          </Alert>
        );

      case CommitIngestionStatusEnum.COMPLETE:
        return renderCompleteView();
      
      default:
        return <div className="space-y-6"><Skeleton className="h-48 w-full" /><Skeleton className="h-64 w-full" /></div>;
    }
  };
  
  const renderCompleteView = () => {
    const details = commitData?.details;
    if (!details) return <Alert variant="destructive">Data marked complete, but details are missing.</Alert>;
    
    const inferenceJobs = commitData?.inference_jobs || [];
    const hasInferenceJobs = inferenceJobs.length > 0;
    
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle>Commit Info</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-sm">
                <div className="flex items-center gap-2"><User className="h-4 w-4 text-muted-foreground"/><p>{details.author_name} &lt;{details.author_email}&gt;</p></div>
                <div className="flex items-center gap-2"><Calendar className="h-4 w-4 text-muted-foreground"/><p>{formatDate(details.author_date)}</p></div>
                
                <div>
                    <Label className="text-xs uppercase text-muted-foreground">Parents</Label>
                    <div className="font-mono text-xs space-y-1 mt-1">
                        {details.parents.map(p => <p key={p} className="truncate"><Link className="text-primary hover:underline" href={`/repositories/${repoId}/commits/${p}`}>{p}</Link></p>)}
                    </div>
                </div>

                <div className="pt-2">
                    <Label className="text-xs uppercase text-muted-foreground flex items-center"><MessageSquare className="h-3.5 w-3.5 mr-1"/>Commit Message</Label>
                    <ScrollArea className="h-32 rounded-md border bg-muted p-3 mt-1">
                        <pre className="whitespace-pre-wrap font-sans text-xs">
                            {details.message}
                        </pre>
                    </ScrollArea>
                </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center"><Lightbulb className="mr-2 h-4 w-4 text-primary" />Prediction Insights</CardTitle></CardHeader>
            <CardContent>
                {hasInferenceJobs ? (
                    <div className="space-y-3">
                        <p className="text-sm text-muted-foreground">This commit has been analyzed. Showing the last {Math.min(5, inferenceJobs.length)} jobs.</p>
                        <ul className="space-y-2">
                            {inferenceJobs.slice(0, 5).map(job => (
                                <li key={job.id} className="text-xs flex justify-between items-center border-b pb-1 last:border-0">
                                    <Link href={`/prediction-insights/${job.id}`} className="text-primary hover:underline">Job #{job.id}</Link>
                                    <Badge variant={job.prediction_result?.commit_prediction === 1 ? 'destructive' : 'secondary'}>{job.prediction_result?.commit_prediction === 1 ? 'Defect' : 'Clean'}</Badge>
                                </li>
                            ))}
                        </ul>
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">No inference jobs have been run for this commit yet.</p>
                )}
            </CardContent>
            <CardFooter>
                {hasInferenceJobs ? (
                    <Button className="w-full" asChild>
                        {/* We don't have a pre-filtered insights page yet, so link to main page */}
                        <Link href={`/prediction-insights`}><Eye className="mr-2 h-4 w-4"/>View All Insights</Link>
                    </Button>
                ) : (
                    <Button className="w-full" asChild>
                        <Link href={`/jobs/inference?repositoryId=${repoId}&commitHash=${commitHash}`}><Play className="mr-2 h-4 w-4"/>Run Inference</Link>
                    </Button>
                )}
            </CardFooter>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>File Changes ({details.stats_files_changed})</CardTitle>
            <CardDescription className="flex gap-4">
              <span className="text-green-600">++ {details.stats_insertions} additions</span>
              <span className="text-red-600">-- {details.stats_deletions} deletions</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Accordion type="single" collapsible className="w-full">
              {details.file_diffs.map(diff => (
                <AccordionItem key={diff.id} value={`file-${diff.id}`}>
                  <AccordionTrigger>
                      <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4"/>
                          <span className="font-mono text-sm">{diff.file_path}</span>
                          <Badge variant="secondary">{diff.change_type}</Badge>
                      </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <FileDiffViewer diffText={diff.diff_text} />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>
      </div>
    );
  };
  
  return (
    <MainLayout>
      <PageContainer
        title={`Commit: ${commitHash.substring(0, 12)}...`}
        description={
          repository ? (
            <Link href={`/repositories/${repository.id}`} className="text-sm text-primary hover:underline">
              In repository: {repository.name}
            </Link>
          ) : (
            <span className="text-sm text-muted-foreground">In repository ID: {repoId}</span>
          )
        }
      >
        {renderStatus()}
      </PageContainer>
    </MainLayout>
  );
}

export default CommitDetailPage;