"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { GitBranch, Search, BarChart3, Database, ArrowRight, Lock, Moon, Sun, Minimize, Maximize } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useTheme } from "@/components/theme-provider"

// Mock data for public repositories
const publicRepositories = [
  {
    id: "pub-1",
    name: "tensorflow/tensorflow",
    description: "An open source machine learning framework for everyone",
    stars: 178000,
    language: "C++",
    models: 12,
    datasets: 8,
    lastUpdated: "2023-04-15T10:30:00Z",
  },
  {
    id: "pub-2",
    name: "facebook/react",
    description: "A declarative, efficient, and flexible JavaScript library for building user interfaces",
    stars: 210000,
    language: "JavaScript",
    models: 8,
    datasets: 5,
    lastUpdated: "2023-04-10T14:20:00Z",
  },
  {
    id: "pub-3",
    name: "microsoft/vscode",
    description: "Visual Studio Code",
    stars: 145000,
    language: "TypeScript",
    models: 15,
    datasets: 10,
    lastUpdated: "2023-04-12T09:15:00Z",
  },
  {
    id: "pub-4",
    name: "django/django",
    description: "The Web framework for perfectionists with deadlines",
    stars: 68000,
    language: "Python",
    models: 6,
    datasets: 4,
    lastUpdated: "2023-04-08T16:45:00Z",
  },
  {
    id: "pub-5",
    name: "flutter/flutter",
    description: "Flutter makes it easy and fast to build beautiful apps for mobile and beyond",
    stars: 152000,
    language: "Dart",
    models: 9,
    datasets: 6,
    lastUpdated: "2023-04-05T11:20:00Z",
  },
]

// Mock data for public models
const publicModels = [
  {
    id: "model-1",
    name: "TensorFlow Bug Predictor",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    type: "RandomForest",
    accuracy: 0.87,
    f1Score: 0.85,
    dateCreated: "2023-04-16T10:20:00Z",
    creator: "ai-team",
  },
  {
    id: "model-2",
    name: "React Component Defect Detector",
    repository: "facebook/react",
    repositoryId: "pub-2",
    type: "XGBoost",
    accuracy: 0.84,
    f1Score: 0.82,
    dateCreated: "2023-04-17T09:15:00Z",
    creator: "web-quality",
  },
  {
    id: "model-3",
    name: "VSCode Extension Bug Finder",
    repository: "microsoft/vscode",
    repositoryId: "pub-3",
    type: "RandomForest",
    accuracy: 0.89,
    f1Score: 0.88,
    dateCreated: "2023-04-14T11:30:00Z",
    creator: "ms-research",
  },
  {
    id: "model-4",
    name: "Django Security Issue Detector",
    repository: "django/django",
    repositoryId: "pub-4",
    type: "LogisticRegression",
    accuracy: 0.82,
    f1Score: 0.79,
    dateCreated: "2023-04-12T14:45:00Z",
    creator: "web-security",
  },
  {
    id: "model-5",
    name: "Flutter UI Bug Predictor",
    repository: "flutter/flutter",
    repositoryId: "pub-5",
    type: "XGBoost",
    accuracy: 0.86,
    f1Score: 0.84,
    dateCreated: "2023-04-10T16:30:00Z",
    creator: "mobile-quality",
  },
]

export default function PublicRepositoriesPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [activeTab, setActiveTab] = useState("repositories")
  const { isAuthenticated } = useAuth()
  const router = useRouter()
  const { toast } = useToast()
  const { theme, setTheme } = useTheme()
  const [isCompact, setIsCompact] = useState(false)

  // Initialize compact view from localStorage
  useEffect(() => {
    const storedCompactView = localStorage.getItem("ck-guru-compact-view")
    if (storedCompactView === "true") {
      document.body.classList.add("compact-view")
      setIsCompact(true)
    }
  }, [])

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  const toggleCompactView = () => {
    const newCompactView = !isCompact
    setIsCompact(newCompactView)

    if (newCompactView) {
      document.body.classList.add("compact-view")
      localStorage.setItem("ck-guru-compact-view", "true")
    } else {
      document.body.classList.remove("compact-view")
      localStorage.setItem("ck-guru-compact-view", "false")
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleCreateDataset = (repoId: string) => {
    if (isAuthenticated) {
      router.push(`/datasets/create?repository=${repoId}`)
    } else {
      toast({
        title: "Authentication required",
        description: "Please sign in to create datasets and models",
      })
      router.push("/login")
    }
  }

  const filteredRepositories = publicRepositories.filter((repo) =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  const filteredModels = publicModels.filter(
    (model) =>
      model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.repository.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 flex h-16 items-center gap-4 border-b bg-background px-6 md:px-8">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <GitBranch className="h-6 w-6 text-primary" />
          <span>CK-Guru</span>
        </Link>
        <nav className="hidden md:flex flex-1 items-center gap-6 text-sm">
          <Link href="/#features" className="text-muted-foreground hover:text-foreground transition-colors">
            Features
          </Link>
          <Link href="/#how-it-works" className="text-muted-foreground hover:text-foreground transition-colors">
            How It Works
          </Link>
          <Link href="/public-repositories" className="text-primary font-medium">
            Public Repositories
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            className="mr-1"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            <span className="sr-only">Toggle theme</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleCompactView}
            className="mr-2"
            title={isCompact ? "Switch to normal view" : "Switch to compact view"}
          >
            {isCompact ? <Maximize className="h-5 w-5" /> : <Minimize className="h-5 w-5" />}
            <span className="sr-only">Toggle compact view</span>
          </Button>

          {isAuthenticated ? (
            <Button asChild>
              <Link href="/dashboard">Go to Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild>
                <Link href="/register">Sign up</Link>
              </Button>
            </>
          )}
        </div>
      </header>

      <main className="flex-1 container mx-auto py-8 px-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Public Repositories</h1>
            <p className="text-muted-foreground mt-1">
              Explore public repositories and pre-trained defect prediction models
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-full md:w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search repositories..."
                className="pl-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            {isAuthenticated ? (
              <Button asChild>
                <Link href="/repositories">My Repositories</Link>
              </Button>
            ) : (
              <Button asChild>
                <Link href="/login">
                  Sign in
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            )}
          </div>
        </div>

        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Want to create your own models?</CardTitle>
            <CardDescription>
              Sign in to create custom datasets and train models for any public or private repository
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              CK-Guru allows you to create personalized defect prediction models tailored to your specific needs. Access
              advanced features like custom cleaning rules, feature selection, and model comparison.
            </p>
          </CardContent>
          <CardFooter>
            {isAuthenticated ? (
              <Button asChild>
                <Link href="/repositories">Go to My Repositories</Link>
              </Button>
            ) : (
              <Button asChild>
                <Link href="/register">Create Free Account</Link>
              </Button>
            )}
          </CardFooter>
        </Card>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="repositories">Repositories</TabsTrigger>
            <TabsTrigger value="models">Pre-trained Models</TabsTrigger>
          </TabsList>

          <TabsContent value="repositories" className="space-y-4">
            {filteredRepositories.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No repositories found matching your search</p>
              </div>
            ) : (
              filteredRepositories.map((repo) => (
                <Card key={repo.id} className="overflow-hidden">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-xl">
                          <Link href={`/public-repositories/${repo.id}`} className="hover:underline">
                            {repo.name}
                          </Link>
                        </CardTitle>
                        <CardDescription className="mt-1">{repo.description}</CardDescription>
                      </div>
                      <Badge variant="outline" className="bg-muted/50">
                        {repo.language}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-4 text-sm">
                      <div className="flex items-center gap-1">
                        <GitBranch className="h-4 w-4 text-muted-foreground" />
                        <span>{repo.stars.toLocaleString()} stars</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <BarChart3 className="h-4 w-4 text-muted-foreground" />
                        <span>{repo.models} models</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <span>{repo.datasets} datasets</span>
                      </div>
                      <div className="text-muted-foreground">Updated {formatDate(repo.lastUpdated)}</div>
                    </div>
                  </CardContent>
                  <CardFooter className="bg-muted/20 border-t flex justify-between">
                    <Button variant="outline" asChild>
                      <Link href={`/public-repositories/${repo.id}`}>View Details</Link>
                    </Button>
                    <Button onClick={() => handleCreateDataset(repo.id)}>
                      {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                      Create Dataset
                    </Button>
                  </CardFooter>
                </Card>
              ))
            )}
          </TabsContent>

          <TabsContent value="models" className="space-y-4">
            {filteredModels.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No models found matching your search</p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredModels.map((model) => (
                  <Card key={model.id}>
                    <CardHeader>
                      <CardTitle className="text-lg">{model.name}</CardTitle>
                      <CardDescription>
                        <Link href={`/public-repositories/${model.repositoryId}`} className="hover:underline">
                          {model.repository}
                        </Link>
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Type:</span>
                          <Badge variant="outline">{model.type}</Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Accuracy:</span>
                          <span className="font-medium">{model.accuracy.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">F1 Score:</span>
                          <span className="font-medium">{model.f1Score.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Created:</span>
                          <span>{formatDate(model.dateCreated)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Creator:</span>
                          <span>{model.creator}</span>
                        </div>
                      </div>
                    </CardContent>
                    <CardFooter className="border-t flex justify-between">
                      <Button variant="outline" asChild>
                        <Link href={`/public-repositories/models/${model.id}`}>View Details</Link>
                      </Button>
                      {!isAuthenticated ? (
                        <Button variant="secondary" asChild>
                          <Link href="/login">
                            <Lock className="mr-2 h-4 w-4" />
                            Use Model
                          </Link>
                        </Button>
                      ) : (
                        <Button variant="secondary" asChild>
                          <Link href={`/jobs/inference?model=${model.id}`}>Use Model</Link>
                        </Button>
                      )}
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </main>

      <footer className="bg-muted/30 py-8 border-t mt-12">
        <div className="container mx-auto px-4 text-center">
          <p className="text-muted-foreground">&copy; {new Date().getFullYear()} CK-Guru. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
