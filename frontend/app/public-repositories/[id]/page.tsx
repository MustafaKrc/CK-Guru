"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { GitBranch, ArrowLeft, Star, GitFork, Eye, Calendar, Lock, ArrowRight } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

// Mock data for public repositories
const publicRepositories = [
  {
    id: "pub-1",
    name: "tensorflow/tensorflow",
    description: "An open source machine learning framework for everyone",
    stars: 178000,
    forks: 89000,
    watchers: 5600,
    language: "C++",
    models: 12,
    datasets: 8,
    lastUpdated: "2023-04-15T10:30:00Z",
    created: "2015-11-07T01:19:20Z",
    url: "https://github.com/tensorflow/tensorflow",
  },
  {
    id: "pub-2",
    name: "facebook/react",
    description: "A declarative, efficient, and flexible JavaScript library for building user interfaces",
    stars: 210000,
    forks: 43000,
    watchers: 6700,
    language: "JavaScript",
    models: 8,
    datasets: 5,
    lastUpdated: "2023-04-10T14:20:00Z",
    created: "2013-05-24T16:15:54Z",
    url: "https://github.com/facebook/react",
  },
  {
    id: "pub-3",
    name: "microsoft/vscode",
    description: "Visual Studio Code",
    stars: 145000,
    forks: 25000,
    watchers: 3200,
    language: "TypeScript",
    models: 15,
    datasets: 10,
    lastUpdated: "2023-04-12T09:15:00Z",
    created: "2015-09-03T20:23:38Z",
    url: "https://github.com/microsoft/vscode",
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
    precision: 0.86,
    recall: 0.84,
    dateCreated: "2023-04-16T10:20:00Z",
    creator: "ai-team",
    description: "Predicts potential bugs in TensorFlow code based on historical data",
  },
  {
    id: "model-2",
    name: "TensorFlow Security Detector",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    type: "XGBoost",
    accuracy: 0.89,
    f1Score: 0.88,
    precision: 0.9,
    recall: 0.86,
    dateCreated: "2023-04-18T14:30:00Z",
    creator: "security-research",
    description: "Specialized model for detecting security vulnerabilities in TensorFlow code",
  },
  {
    id: "model-3",
    name: "TensorFlow Performance Issue Finder",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    type: "LogisticRegression",
    accuracy: 0.82,
    f1Score: 0.8,
    precision: 0.81,
    recall: 0.79,
    dateCreated: "2023-04-20T09:45:00Z",
    creator: "performance-team",
    description: "Identifies code changes that might lead to performance degradation",
  },
]

// Mock data for public datasets
const publicDatasets = [
  {
    id: "dataset-1",
    name: "TensorFlow Core Dataset",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    status: "Ready",
    dateCreated: "2023-04-10T08:30:00Z",
    creator: "ai-team",
    description: "Core dataset with CK metrics and commit history for TensorFlow",
    features: 24,
    samples: 15000,
  },
  {
    id: "dataset-2",
    name: "TensorFlow Extended Features",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    status: "Ready",
    dateCreated: "2023-04-12T11:15:00Z",
    creator: "data-science",
    description: "Extended dataset with additional code metrics and bot filtering",
    features: 36,
    samples: 12000,
  },
  {
    id: "dataset-3",
    name: "TensorFlow Security Focus",
    repository: "tensorflow/tensorflow",
    repositoryId: "pub-1",
    status: "Ready",
    dateCreated: "2023-04-14T15:40:00Z",
    creator: "security-research",
    description: "Dataset focused on security-related metrics and vulnerabilities",
    features: 18,
    samples: 8000,
  },
]

export default function PublicRepositoryDetailPage({ params }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState("overview")
  const { isAuthenticated } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  // Find the repository by ID
  const repository = publicRepositories.find((repo) => repo.id === params.id)

  // Filter models and datasets for this repository
  const repositoryModels = publicModels.filter((model) => model.repositoryId === params.id)
  const repositoryDatasets = publicDatasets.filter((dataset) => dataset.repositoryId === params.id)

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleCreateDataset = () => {
    if (isAuthenticated) {
      router.push(`/datasets/create?repository=${params.id}`)
    } else {
      toast({
        title: "Authentication required",
        description: "Please sign in to create datasets and models",
      })
      router.push("/login")
    }
  }

  if (!repository) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center">
        <h1 className="text-2xl font-bold mb-4">Repository not found</h1>
        <Button asChild>
          <Link href="/public-repositories">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Public Repositories
          </Link>
        </Button>
      </div>
    )
  }

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
        <div className="flex items-center gap-4 mb-6">
          <Button variant="outline" size="icon" asChild>
            <Link href="/public-repositories">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{repository.name}</h1>
            <p className="text-muted-foreground">{repository.description}</p>
          </div>
        </div>

        {!isAuthenticated && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Want to create your own models for this repository?</CardTitle>
              <CardDescription>Sign in to create custom datasets and train models</CardDescription>
            </CardHeader>
            <CardContent className="flex justify-between items-center">
              <p className="text-muted-foreground max-w-2xl">
                Create personalized defect prediction models tailored to your specific needs with advanced features like
                custom cleaning rules, feature selection, and model comparison.
              </p>
              <Button asChild>
                <Link href="/register">
                  Create Free Account
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="models">Models ({repositoryModels.length})</TabsTrigger>
            <TabsTrigger value="datasets">Datasets ({repositoryDatasets.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Stars</CardTitle>
                  <Star className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{repository.stars.toLocaleString()}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Forks</CardTitle>
                  <GitFork className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{repository.forks.toLocaleString()}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Watchers</CardTitle>
                  <Eye className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{repository.watchers.toLocaleString()}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Created</CardTitle>
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{new Date(repository.created).getFullYear()}</div>
                  <p className="text-xs text-muted-foreground">{formatDate(repository.created)}</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Repository Information</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-4">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Name:</dt>
                      <dd className="font-medium">{repository.name}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Primary Language:</dt>
                      <dd>
                        <Badge variant="outline">{repository.language}</Badge>
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Last Updated:</dt>
                      <dd>{formatDate(repository.lastUpdated)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">GitHub URL:</dt>
                      <dd>
                        <a
                          href={repository.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline"
                        >
                          View on GitHub
                        </a>
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Defect Prediction Stats</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-4">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Available Models:</dt>
                      <dd className="font-medium">{repository.models}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Available Datasets:</dt>
                      <dd className="font-medium">{repository.datasets}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Best Model Accuracy:</dt>
                      <dd className="font-medium">
                        {Math.max(...repositoryModels.map((model) => model.accuracy)).toFixed(2)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Best F1 Score:</dt>
                      <dd className="font-medium">
                        {Math.max(...repositoryModels.map((model) => model.f1Score)).toFixed(2)}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            </div>

            <div className="flex justify-end">
              <Button onClick={handleCreateDataset}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Create Custom Dataset
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="models" className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">Available Models</h2>
              <Button onClick={handleCreateDataset}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Train New Model
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {repositoryModels.map((model) => (
                <Card key={model.id}>
                  <CardHeader>
                    <CardTitle className="text-lg">{model.name}</CardTitle>
                    <CardDescription>{model.description}</CardDescription>
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
                        <span className="text-muted-foreground">Precision:</span>
                        <span>{model.precision.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Recall:</span>
                        <span>{model.recall.toFixed(2)}</span>
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
                  <CardContent className="border-t pt-4">
                    <div className="flex justify-between">
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
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="datasets" className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">Available Datasets</h2>
              <Button onClick={handleCreateDataset}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Create Custom Dataset
              </Button>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Dataset Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Features</TableHead>
                    <TableHead>Samples</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Creator</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {repositoryDatasets.map((dataset) => (
                    <TableRow key={dataset.id}>
                      <TableCell className="font-medium">{dataset.name}</TableCell>
                      <TableCell>{dataset.description}</TableCell>
                      <TableCell>{dataset.features}</TableCell>
                      <TableCell>{dataset.samples.toLocaleString()}</TableCell>
                      <TableCell>{formatDate(dataset.dateCreated)}</TableCell>
                      <TableCell>{dataset.creator}</TableCell>
                      <TableCell className="text-right">
                        {!isAuthenticated ? (
                          <Button variant="outline" size="sm" asChild>
                            <Link href="/login">
                              <Lock className="mr-2 h-4 w-4" />
                              View Data
                            </Link>
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm" asChild>
                            <Link href={`/datasets/${dataset.id}`}>View Data</Link>
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
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
