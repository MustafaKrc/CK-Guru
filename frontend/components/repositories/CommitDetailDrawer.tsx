// frontend/components/repositories/CommitDetailDrawer.tsx
"use client";

import React, { useState, useEffect } from 'react';
import { CommitPageResponse } from '@/types/api';
import { apiService, handleApiError } from '@/lib/apiService';

import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription, DrawerClose } from '@/components/ui/drawer';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { FileDiffViewer } from '@/components/commits/FileDiffViewer';
import { FileText, User, Calendar } from 'lucide-react';

interface CommitDetailDrawerProps {
  repoId: string;
  commitHash: string | null;
  repoName: string;
  onOpenChange: (isOpen: boolean) => void;
}

export const CommitDetailDrawer: React.FC<CommitDetailDrawerProps> = ({ repoId, commitHash, repoName, onOpenChange }) => {
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
        } else {
            setDetails(null);
        }
    }, [repoId, commitHash]);

    const renderContent = () => {
        if (isLoading) {
            return <div className="p-6 space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>;
        }
        if (!details?.details) {
            return <div className="p-6 text-muted-foreground">Could not load commit details.</div>;
        }
        return (
             <ScrollArea className="h-full">
                <div className="p-6 space-y-6">
                    <Card>
                        <CardHeader><CardTitle>Commit Info</CardTitle></CardHeader>
                        <CardContent className="text-sm space-y-3">
                            <div className="flex items-center gap-2"><User className="h-4 w-4 text-muted-foreground"/><p>{details.details.author_name} &lt;{details.details.author_email}&gt;</p></div>
                            <div className="flex items-center gap-2"><Calendar className="h-4 w-4 text-muted-foreground"/><p>{new Date(details.details.author_date).toLocaleString()}</p></div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader><CardTitle>Commit Message</CardTitle></CardHeader>
                        <CardContent><pre className="whitespace-pre-wrap font-sans text-sm">{details.details.message}</pre></CardContent>
                    </Card>
                    <Card>
                        <CardHeader><CardTitle>File Changes ({details.details.file_diffs.length})</CardTitle></CardHeader>
                        <CardContent>
                            <Accordion type="single" collapsible className="w-full">
                                {details.details.file_diffs.map(diff => (
                                    <AccordionItem key={diff.id} value={`diff-${diff.id}`}>
                                        <AccordionTrigger>
                                            <div className="flex items-center gap-2">
                                                <FileText className="h-4 w-4"/>
                                                <span className="font-mono text-sm">{diff.file_path}</span>
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
        <Drawer open={!!commitHash} onOpenChange={onOpenChange}>
            <DrawerContent className="h-[90vh]">
                <DrawerHeader className="flex-shrink-0">
                    <DrawerTitle>Commit Details: {commitHash?.substring(0,12)}...</DrawerTitle>
                    <DrawerDescription>In repository {repoName}.</DrawerDescription>
                </DrawerHeader>
                <div className="flex-grow overflow-auto">
                    {renderContent()}
                </div>
                <DrawerClose asChild><Button variant="outline" className="absolute top-4 right-4">Close</Button></DrawerClose>
            </DrawerContent>
        </Drawer>
    );
};