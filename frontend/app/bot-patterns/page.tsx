"use client"

import type React from "react"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Plus, MoreHorizontal, Edit, Trash2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useSearchParams } from "next/navigation"

// Mock repositories for selection
const mockRepositories = [
  { id: "1", name: "frontend-app" },
  { id: "2", name: "backend-api" },
  { id: "3", name: "mobile-client" },
  { id: "4", name: "shared-lib" },
]

// Mock global bot patterns
const mockGlobalPatterns = [
  {
    id: "1",
    pattern: "dependabot",
    type: "Exact",
    isExclusion: false,
    description: "Dependabot automated dependency updates",
  },
  {
    id: "2",
    pattern: "*bot*",
    type: "Wildcard",
    isExclusion: false,
    description: "Any commit author containing 'bot'",
  },
  {
    id: "3",
    pattern: "^\\[automated\\].*",
    type: "Regex",
    isExclusion: false,
    description: "Commit messages starting with [automated]",
  },
  {
    id: "4",
    pattern: "john.doe@example.com",
    type: "Exact",
    isExclusion: true,
    description: "Exclude this specific email from bot detection",
  },
]

// Mock repository-specific patterns
const mockRepoPatterns = {
  "1": [
    {
      id: "r1-1",
      pattern: "frontend-ci",
      type: "Exact",
      isExclusion: false,
      description: "Frontend CI automation",
    },
  ],
  "2": [
    {
      id: "r2-1",
      pattern: "backend-deploy-*",
      type: "Wildcard",
      isExclusion: false,
      description: "Backend deployment automation",
    },
  ],
}

export default function BotPatternsPage() {
  const searchParams = useSearchParams()
  const preselectedRepoId = searchParams.get("repository")

  const [activeTab, setActiveTab] = useState(preselectedRepoId ? "repository" : "global")
  const [selectedRepository, setSelectedRepository] = useState(preselectedRepoId || "")
  const [globalPatterns, setGlobalPatterns] = useState(mockGlobalPatterns)
  const [repoPatterns, setRepoPatterns] = useState(mockRepoPatterns)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingPattern, setEditingPattern] = useState<any>(null)
  const [formData, setFormData] = useState({
    pattern: "",
    type: "Exact",
    isExclusion: false,
    description: "",
  })

  const { toast } = useToast()

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleCheckboxChange = (checked: boolean) => {
    setFormData((prev) => ({ ...prev, isExclusion: checked }))
  }

  const handleRepositoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedRepository(e.target.value)
  }

  const handleAddPattern = () => {
    setEditingPattern(null)
    setFormData({
      pattern: "",
      type: "Exact",
      isExclusion: false,
      description: "",
    })
    setDialogOpen(true)
  }

  const handleEditPattern = (pattern: any) => {
    setEditingPattern(pattern)
    setFormData({
      pattern: pattern.pattern,
      type: pattern.type,
      isExclusion: pattern.isExclusion,
      description: pattern.description,
    })
    setDialogOpen(true)
  }

  const handleDeletePattern = (patternId: string, isGlobal: boolean) => {
    if (isGlobal) {
      setGlobalPatterns((prev) => prev.filter((p) => p.id !== patternId))
    } else {
      if (!selectedRepository) return

      setRepoPatterns((prev) => ({
        ...prev,
        [selectedRepository]: prev[selectedRepository]?.filter((p) => p.id !== patternId) || [],
      }))
    }

    toast({
      title: "Pattern deleted",
      description: "The bot pattern has been deleted successfully",
    })
  }

  const handleSubmit = () => {
    // Validate
    if (!formData.pattern.trim()) {
      toast({
        title: "Missing information",
        description: "Please enter a pattern string",
        variant: "destructive",
      })
      return
    }

    const newPattern = {
      id: editingPattern ? editingPattern.id : `${Date.now()}`,
      ...formData,
    }

    if (activeTab === "global") {
      if (editingPattern) {
        setGlobalPatterns((prev) => prev.map((p) => (p.id === editingPattern.id ? newPattern : p)))
      } else {
        setGlobalPatterns((prev) => [...prev, newPattern])
      }
    } else {
      if (!selectedRepository) return

      if (editingPattern) {
        setRepoPatterns((prev) => ({
          ...prev,
          [selectedRepository]:
            prev[selectedRepository]?.map((p) => (p.id === editingPattern.id ? newPattern : p)) || [],
        }))
      } else {
        setRepoPatterns((prev) => ({
          ...prev,
          [selectedRepository]: [...(prev[selectedRepository] || []), newPattern],
        }))
      }
    }

    setDialogOpen(false)

    toast({
      title: editingPattern ? "Pattern updated" : "Pattern added",
      description: `The bot pattern has been ${editingPattern ? "updated" : "added"} successfully`,
    })
  }

  const getPatternTypeBadge = (type: string) => {
    switch (type) {
      case "Exact":
        return <Badge variant="outline">Exact</Badge>
      case "Wildcard":
        return <Badge variant="secondary">Wildcard</Badge>
      case "Regex":
        return <Badge>Regex</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Bot Patterns</h1>
          <Button onClick={handleAddPattern}>
            <Plus className="mr-2 h-4 w-4" />
            Add Pattern
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="global">Global Patterns</TabsTrigger>
            <TabsTrigger value="repository">Repository Patterns</TabsTrigger>
          </TabsList>

          <TabsContent value="global" className="space-y-4">
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Pattern</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Exclusion</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {globalPatterns.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-4 text-muted-foreground">
                        No global patterns defined yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    globalPatterns.map((pattern) => (
                      <TableRow key={pattern.id}>
                        <TableCell className="font-mono">{pattern.pattern}</TableCell>
                        <TableCell>{getPatternTypeBadge(pattern.type)}</TableCell>
                        <TableCell>
                          <Checkbox checked={pattern.isExclusion} disabled />
                        </TableCell>
                        <TableCell>{pattern.description}</TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                                <span className="sr-only">Open menu</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleEditPattern(pattern)}>
                                <Edit className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={() => handleDeletePattern(pattern.id, true)}
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
          </TabsContent>

          <TabsContent value="repository" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="repository">Select Repository</Label>
              <select
                id="repository"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={selectedRepository}
                onChange={handleRepositoryChange}
              >
                <option value="">Select a repository</option>
                {mockRepositories.map((repo) => (
                  <option key={repo.id} value={repo.id}>
                    {repo.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedRepository ? (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Pattern</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Exclusion</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {!repoPatterns[selectedRepository] || repoPatterns[selectedRepository].length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center py-4 text-muted-foreground">
                          No repository-specific patterns defined yet
                        </TableCell>
                      </TableRow>
                    ) : (
                      repoPatterns[selectedRepository].map((pattern) => (
                        <TableRow key={pattern.id}>
                          <TableCell className="font-mono">{pattern.pattern}</TableCell>
                          <TableCell>{getPatternTypeBadge(pattern.type)}</TableCell>
                          <TableCell>
                            <Checkbox checked={pattern.isExclusion} disabled />
                          </TableCell>
                          <TableCell>{pattern.description}</TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                  <span className="sr-only">Open menu</span>
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleEditPattern(pattern)}>
                                  <Edit className="mr-2 h-4 w-4" />
                                  Edit
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => handleDeletePattern(pattern.id, false)}
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
            ) : (
              <div className="rounded-md border p-8 text-center text-muted-foreground">
                Please select a repository to view or add repository-specific patterns
              </div>
            )}
          </TabsContent>
        </Tabs>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingPattern ? "Edit Bot Pattern" : "Add Bot Pattern"}</DialogTitle>
              <DialogDescription>
                {activeTab === "global"
                  ? "Define a pattern to identify bot commits across all repositories"
                  : `Define a pattern specific to the ${mockRepositories.find((r) => r.id === selectedRepository)?.name} repository`}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="pattern">Pattern String</Label>
                <Input
                  id="pattern"
                  name="pattern"
                  placeholder="e.g., dependabot or *bot*"
                  value={formData.pattern}
                  onChange={handleInputChange}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="type">Pattern Type</Label>
                <select
                  id="type"
                  name="type"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={formData.type}
                  onChange={handleInputChange}
                >
                  <option value="Exact">Exact</option>
                  <option value="Wildcard">Wildcard</option>
                  <option value="Regex">Regex</option>
                </select>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox id="isExclusion" checked={formData.isExclusion} onCheckedChange={handleCheckboxChange} />
                <Label htmlFor="isExclusion">
                  Exclusion Pattern (prevents matching commits from being identified as bots)
                </Label>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  name="description"
                  placeholder="Describe what this pattern is intended to match"
                  value={formData.description}
                  onChange={handleInputChange}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit}>{editingPattern ? "Update" : "Add"} Pattern</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  )
}
