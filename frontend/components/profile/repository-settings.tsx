"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  GitBranch,
  Plus,
  MoreHorizontal,
  RefreshCw,
  Eye,
  Edit,
  Trash2,
  GitFork,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// Mock data for user repositories
const mockUserRepositories = [
  {
    id: "user-1",
    name: "my-frontend-app",
    gitUrl: "https://github.com/username/my-frontend-app.git",
    provider: "GitHub",
    dateAdded: "2023-05-10T10:30:00Z",
    status: "Ingested",
    lastIngested: "2023-05-12T14:20:00Z",
    isPrivate: true,
  },
  {
    id: "user-2",
    name: "my-backend-api",
    gitUrl: "https://gitlab.com/username/my-backend-api.git",
    provider: "GitLab",
    dateAdded: "2023-05-08T09:15:00Z",
    status: "Ingesting",
    lastIngested: null,
    isPrivate: true,
  },
  {
    id: "user-3",
    name: "open-source-lib",
    gitUrl: "https://github.com/username/open-source-lib.git",
    provider: "GitHub",
    dateAdded: "2023-05-05T16:45:00Z",
    status: "Not Ingested",
    lastIngested: null,
    isPrivate: false,
  },
];

export function RepositorySettings() {
  const [repositories, setRepositories] = useState(mockUserRepositories);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const router = useRouter();
  const { toast } = useToast();

  const handleAddRepository = () => {
    // Validate URL
    if (!newRepoUrl || !newRepoUrl.trim()) {
      toast({
        title: "Error",
        description: "Please enter a valid Git URL",
        variant: "destructive",
      });
      return;
    }

    // In a real app, this would be an API call
    const provider = newRepoUrl.includes("github.com")
      ? "GitHub"
      : newRepoUrl.includes("gitlab.com")
        ? "GitLab"
        : "Other";
    const newRepo = {
      id: `user-${repositories.length + 1}`,
      name: newRepoUrl.split("/").pop()?.replace(".git", "") || "new-repo",
      gitUrl: newRepoUrl,
      provider,
      dateAdded: new Date().toISOString(),
      status: "Not Ingested",
      lastIngested: null,
      isPrivate: true,
    };

    setRepositories([...repositories, newRepo]);
    setNewRepoUrl("");
    setAddDialogOpen(false);

    toast({
      title: "Repository added",
      description: "The repository has been added successfully",
    });
  };

  const handleDeleteRepository = () => {
    if (!selectedRepo) return;

    // In a real app, this would be an API call
    setRepositories(repositories.filter((repo) => repo.id !== selectedRepo));
    setDeleteDialogOpen(false);

    toast({
      title: "Repository deleted",
      description: "The repository has been deleted successfully",
    });
  };

  const handleIngestRepository = (repoId: string) => {
    // In a real app, this would be an API call
    setRepositories(
      repositories.map((repo) => (repo.id === repoId ? { ...repo, status: "Ingesting" } : repo))
    );

    toast({
      title: "Ingestion started",
      description: "Repository ingestion has been initiated",
    });
  };

  const getStatusBadge = (status: string) => {
    switch (
      status
        .toUpperCase()
        .replace("JOBSTATUSENUM", "")
        .replace("TASKSTATUSENUM", "")
        .replace(".", "")
    ) {
      case "Ingested":
        return <Badge className="status-badge-ready">Ingested</Badge>;
      case "Ingesting":
        return (
          <Badge variant="outline" className="status-badge-running flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Ingesting
          </Badge>
        );
      case "Failed":
        return (
          <Badge variant="destructive" className="status-badge-failed">
            Failed
          </Badge>
        );
      default:
        return <Badge variant="secondary">Not Ingested</Badge>;
    }
  };

  const getProviderBadge = (provider: string, isPrivate: boolean) => {
    switch (provider) {
      case "GitHub":
        return (
          <Badge
            variant="outline"
            className="bg-[#24292e]/10 text-[#24292e] dark:bg-[#24292e]/20 dark:text-white"
          >
            <GitBranch className="mr-1 h-3 w-3" />
            GitHub {isPrivate && "(Private)"}
          </Badge>
        );
      case "GitLab":
        return (
          <Badge
            variant="outline"
            className="bg-[#fc6d26]/10 text-[#fc6d26] dark:bg-[#fc6d26]/20 dark:text-[#fc6d26]"
          >
            <GitFork className="mr-1 h-3 w-3" />
            GitLab {isPrivate && "(Private)"}
          </Badge>
        );
      default:
        return <Badge variant="outline">Other</Badge>;
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>Your Repositories</CardTitle>
            <CardDescription>Manage your connected Git repositories</CardDescription>
          </div>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Repository
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Repository</DialogTitle>
                <DialogDescription>
                  Enter the Git URL of the repository you want to add.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="git-url">Git URL</Label>
                  <Input
                    id="git-url"
                    placeholder="https://github.com/username/repo.git"
                    value={newRepoUrl}
                    onChange={(e) => setNewRepoUrl(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Make sure you have added the appropriate integration in the Integrations tab for
                    private repositories.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddRepository}>Add Repository</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Repository Name</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Date Added</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {repositories.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-4 text-muted-foreground">
                      No repositories added yet. Add your first repository to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  repositories.map((repo) => (
                    <TableRow key={repo.id}>
                      <TableCell className="font-medium">{repo.name}</TableCell>
                      <TableCell>{getProviderBadge(repo.provider, repo.isPrivate)}</TableCell>
                      <TableCell>{formatDate(repo.dateAdded)}</TableCell>
                      <TableCell>
                        {getStatusBadge(repo.status)}
                        {repo.lastIngested && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Last: {formatDate(repo.lastIngested)}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Open menu</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem
                              onClick={() => router.push(`/repositories/${repo.id}`)}
                            >
                              <Eye className="mr-2 h-4 w-4" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleIngestRepository(repo.id)}
                              disabled={repo.status === "Ingesting"}
                            >
                              <RefreshCw className="mr-2 h-4 w-4" />
                              {repo.status === "Not Ingested" ? "Ingest" : "Re-Ingest"}
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => {
                                setSelectedRepo(repo.id);
                                setDeleteDialogOpen(true);
                              }}
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
        </CardContent>
      </Card>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Repository</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this repository? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteRepository}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
