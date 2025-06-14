// app/bot-patterns/page.tsx
"use client";

import React, { useState, useEffect, useCallback, Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  MoreHorizontal,
  Edit,
  Trash2,
  Check,
  X,
  Loader2,
  AlertCircle,
  Info,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { PageLoader } from "@/components/ui/page-loader";
import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import {
  BotPatternRead,
  BotPatternCreatePayload,
  BotPatternUpdatePayload,
  Repository,
} from "@/types/api";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Combobox } from "@/components/ui/combobox";

function BotPatternsPageContent() {
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const preselectedRepoId = searchParams.get("repository");

  const [activeTab, setActiveTab] = useState(preselectedRepoId ? "repository" : "global");
  const [selectedRepositoryId, setSelectedRepositoryId] = useState<string>(preselectedRepoId || "");
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);

  const [globalPatterns, setGlobalPatterns] = useState<BotPatternRead[]>([]);
  const [repoPatterns, setRepoPatterns] = useState<BotPatternRead[]>([]);
  const [isLoadingPatterns, setIsLoadingPatterns] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [editingPattern, setEditingPattern] = useState<BotPatternRead | null>(null);
  const [formData, setFormData] = useState<Partial<BotPatternCreatePayload>>({});

  const [dialogContext, setDialogContext] = useState<{
    scope: "global" | "repository";
    repoName?: string;
  }>({ scope: "global" });

  const fetchRepositories = useCallback(async () => {
    setIsLoadingRepos(true);
    try {
      const response = await apiService.getRepositories({ limit: 500 });
      setRepositories(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load repositories");
    } finally {
      setIsLoadingRepos(false);
    }
  }, []);

  const fetchPatterns = useCallback(async () => {
    setIsLoadingPatterns(true);
    try {
      if (activeTab === "global") {
        const response = await apiService.getGlobalBotPatterns();
        setGlobalPatterns(response.items);
      } else if (activeTab === "repository" && selectedRepositoryId) {
        const response = await apiService.getRepoBotPatterns(parseInt(selectedRepositoryId), {
          include_global: false,
        });
        setRepoPatterns(response.items);
      } else {
        setRepoPatterns([]);
      }
    } catch (err) {
      handleApiError(err, `Failed to fetch ${activeTab} patterns`);
    } finally {
      setIsLoadingPatterns(false);
    }
  }, [activeTab, selectedRepositoryId]);

  useEffect(() => {
    fetchRepositories();
  }, [fetchRepositories]);

  useEffect(() => {
    fetchPatterns();
  }, [fetchPatterns]);

  const handleOpenDialog = (pattern: BotPatternRead | null = null) => {
    const isEditing = !!pattern;
    const currentScope = isEditing ? (pattern.repository_id ? "repository" : "global") : activeTab;

    if (currentScope === "repository" && !selectedRepositoryId && !isEditing) {
      toast({
        title: "No Repository Selected",
        description: "Please select a repository before adding a repository-specific pattern.",
        variant: "destructive",
      });
      return;
    }

    const currentRepo = repositories.find(
      (r) => r.id.toString() === (pattern?.repository_id?.toString() || selectedRepositoryId)
    );

    setDialogContext({
      scope: currentScope as "global" | "repository",
      repoName: currentRepo?.name,
    });

    setEditingPattern(pattern);
    setFormData({
      pattern: pattern?.pattern || "",
      is_exclusion: pattern?.is_exclusion || false,
      description: pattern?.description || "",
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.pattern || !formData.pattern.trim()) {
      toast({
        title: "Validation Error",
        description: "Pattern cannot be empty.",
        variant: "destructive",
      });
      return;
    }
    try {
      new RegExp(formData.pattern);
    } catch (e) {
      toast({
        title: "Invalid Regex",
        description: "The pattern is not a valid regular expression.",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingPattern) {
        const payload: BotPatternUpdatePayload = {
          pattern: formData.pattern,
          is_exclusion: formData.is_exclusion,
          description: formData.description,
        };
        await apiService.updateBotPattern(editingPattern.id, payload);
        toast({ title: "Success", description: "Bot pattern updated successfully." });
      } else {
        const payload: BotPatternCreatePayload = {
          pattern: formData.pattern!,
          is_exclusion: !!formData.is_exclusion,
          description: formData.description,
          repository_id:
            dialogContext.scope === "repository" ? parseInt(selectedRepositoryId) : undefined,
        };
        await apiService.createBotPattern(payload);
        toast({ title: "Success", description: "New bot pattern created." });
      }
      setDialogOpen(false);
      fetchPatterns();
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        toast({
          title: "Invalid Regex",
          description: `Backend error: ${err.message}`,
          variant: "destructive",
        });
      } else {
        handleApiError(err, `Failed to ${editingPattern ? "update" : "create"} pattern`);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (patternId: number) => {
    try {
      await apiService.deleteBotPattern(patternId);
      toast({ title: "Success", description: "Bot pattern deleted." });
      fetchPatterns();
    } catch (err) {
      handleApiError(err, "Failed to delete pattern");
    }
  };

  const currentPatterns = useMemo(
    () => (activeTab === "global" ? globalPatterns : repoPatterns),
    [activeTab, globalPatterns, repoPatterns]
  );

  const repositoryOptions = useMemo(() => {
    return repositories.map((repo) => ({
      value: repo.id.toString(),
      label: repo.name,
    }));
  }, [repositories]);

  const renderTable = (patterns: BotPatternRead[]) => (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Pattern (Regex)</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Type</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoadingPatterns ? (
            Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Skeleton className="h-5 w-48" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-6 w-24" />
                </TableCell>
                <TableCell className="text-right">
                  <Skeleton className="h-8 w-8" />
                </TableCell>
              </TableRow>
            ))
          ) : patterns.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                No patterns found for this scope.
              </TableCell>
            </TableRow>
          ) : (
            patterns.map((pattern) => (
              <TableRow key={pattern.id}>
                <TableCell className="font-mono">{pattern.pattern}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {pattern.description || "N/A"}
                </TableCell>
                <TableCell>
                  <Badge variant={pattern.is_exclusion ? "outline" : "secondary"}>
                    {pattern.is_exclusion ? (
                      <>
                        <X className="mr-1 h-3 w-3" />
                        Exclusion
                      </>
                    ) : (
                      <>
                        <Check className="mr-1 h-3 w-3" />
                        Inclusion
                      </>
                    )}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleOpenDialog(pattern)}>
                        <Edit className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => handleDelete(pattern.id)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer
        title="Bot Patterns"
        description="Manage regex patterns to identify or exclude bot-authored commits during dataset creation."
        actions={
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="mr-2 h-4 w-4" />
            Add Pattern
          </Button>
        }
      >
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="global">Global Patterns</TabsTrigger>
            <TabsTrigger value="repository">Repository-Specific</TabsTrigger>
          </TabsList>
          <TabsContent value="global">{renderTable(globalPatterns)}</TabsContent>
          <TabsContent value="repository" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="repository-select">Select Repository</Label>
              <Combobox
                options={repositoryOptions}
                value={selectedRepositoryId}
                onValueChange={setSelectedRepositoryId}
                disabled={isLoadingRepos}
                placeholder={
                  isLoadingRepos ? "Loading repositories..." : "Search and select a repository..."
                }
                searchPlaceholder="Search repository..."
                emptyMessage="No repository found."
                className="w-full md:w-[350px]"
              />
            </div>
            {selectedRepositoryId ? (
              renderTable(repoPatterns)
            ) : (
              <Alert variant="default" className="text-center py-8">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Please select a repository to view or manage its specific bot patterns.
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>
        </Tabs>
      </PageContainer>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingPattern ? "Edit" : "Create"} Bot Pattern</DialogTitle>
            <DialogDescription>
              Define a regex pattern for author names.
              <Badge
                variant={dialogContext.scope === "global" ? "secondary" : "default"}
                className="ml-2"
              >
                Scope:{" "}
                {dialogContext.scope === "global"
                  ? "Global"
                  : `Repository (${dialogContext.repoName || "..."})`}
              </Badge>
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="pattern">Pattern (Regex) *</Label>
              <Input
                id="pattern"
                value={formData.pattern || ""}
                onChange={(e) => setFormData((p) => ({ ...p, pattern: e.target.value }))}
                placeholder="e.g., .*\[bot\].*"
              />
              <Alert variant="default" className="text-xs p-2 mt-2">
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Uses Python's `re` module flavor. Test your patterns accordingly.
                </AlertDescription>
              </Alert>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description || ""}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                placeholder="A brief note about this pattern's purpose."
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="is_exclusion"
                checked={formData.is_exclusion}
                onCheckedChange={(checked) =>
                  setFormData((p) => ({ ...p, is_exclusion: !!checked }))
                }
              />
              <Label htmlFor="is_exclusion">Exclusion Pattern</Label>
            </div>
            <p className="text-xs text-muted-foreground">
              An **Inclusion** pattern marks a matching author as a bot. An **Exclusion** pattern
              marks a matching author as explicitly NOT a bot, overriding any inclusion matches.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingPattern ? "Save Changes" : "Create Pattern"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}

export default function BotPatternsPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading bot patterns..." />}>
      <BotPatternsPageContent />
    </Suspense>
  );
}
