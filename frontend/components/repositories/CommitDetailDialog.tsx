// frontend/components/repositories/CommitDetailDialog.tsx
"use client";

import React, { useState, useEffect } from 'react';
import { CommitPageResponse } from '@/types/api';
import { apiService, handleApiError } from '@/lib/apiService';

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { FileDiffViewer } from '@/components/commits/FileDiffViewer';
import { FileText, User, Calendar } from 'lucide-react';

interface CommitDetailDialogProps {
  repoId: string;
  commitHash: string | null;
  repoName: string;
  onOpenChange: (isOpen: boolean) => void;
}

export const CommitDetailDialog: React.FC<CommitDetailDialogProps> = ({ repoId, commitHash, repoName, onOpenChange }) => {
    const [details, setDetails] = useState<CommitPageResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (commitHash) {
            const fetchDetails = async () => {
                setIsLoading(true);
                try {
                    const data = await apiService.getCommitDetails(repoId, commitHash);
                    setDetails(data);
                } catch (error) {
                    handleApiError(error, `Failed to load details for commit ${commitHash.substring(0, 7)}`);
                } finally {
                    setIsLoading(false);
                }
            };
            fetchDetails();
        }
    }, [repoId, commitHash]);

    const renderContent = () => {
        if (isLoading) {
            return <div className="p-6 space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>;
        }

        if (!details?.details) {
            return <div className="p-6 text-muted-foreground">Could not load commit details. The commit may not be ingested yet.</div>;
        }

        return (
            <ScrollArea className="max-h-[70vh]">
                <div className="p-1 space-y-4">
                    <Card>
                        <CardHeader className="pb-3"><CardTitle className="text-base">Commit Info</CardTitle></CardHeader>
                        <CardContent className="text-sm space-y-2">
                            <div className="flex items-center gap-2"><User className="h-4 w-4 text-muted-foreground"/><p>{details.details.author_name} &lt;{details.details.author_email}&gt;</p></div>
                            <div className="flex items-center gap-2"><Calendar className="h-4 w-4 text-muted-foreground"/><p>{new Date(details.details.author_date).toLocaleString()}</p></div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-3"><CardTitle className="text-base">Commit Message</CardTitle></CardHeader>
                        <CardContent><pre className="whitespace-pre-wrap font-sans text-sm bg-muted p-3 rounded-md">{details.details.message}</pre></CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-3"><CardTitle className="text-base">File Changes ({details.details.file_diffs.length})</CardTitle></CardHeader>
                        <CardContent>
                            <Accordion type="single" collapsible className="w-full">
                                {details.details.file_diffs.map(diff => (
                                    <AccordionItem key={diff.id} value={`diff-${diff.id}`}>
                                        <AccordionTrigger>
                                            <div className="flex items-center gap-2 text-sm">
                                                <FileText className="h-4 w-4"/>
                                                <span className="font-mono">{diff.file_path}</span>
                                                <Badge variant="outline">{diff.change_type}</Badge>
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
            </ScrollArea>
        );
    };

    return (
        <Dialog open={!!commitHash} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Commit Details: {commitHash?.substring(0,12)}...</DialogTitle>
                    <DialogDescription>In repository {repoName}.</DialogDescription>
                </DialogHeader>
                <div className="flex-grow overflow-hidden relative">
                    {renderContent()}
                </div>
            </DialogContent>
        </Dialog>
    );
};