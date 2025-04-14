"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ArrowLeft, GitBranch, Lock, ArrowRight } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

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
    auc: 0.91,
    dateCreated: "2023-04-16T10:20:00Z",
    creator: "ai-team",
    description: "Predicts potential bugs in TensorFlow code based on historical data",
    features: [
      { name: "CBO", importance: 0.18 },
      { name: "RFC", importance: 0.15 },
      { name: "WMC", importance: 0.12 },
      { name: "LCOM", importance: 0.1 },
      { name: "lines_added", importance: 0.09 },
      { name: "files_changed", importance: 0.08 },
      { name: "commit_hour", importance: 0.07 },
      { name: "commit_day", importance: 0.06 },
      { name: "DIT", importance: 0.05 },
      { name: "NOC", importance: 0.04 },
    ],
    hyperparameters: {
      n_estimators: 100,
      max_depth: 10,
      min_samples_split: 2,
      min_samples_leaf: 1,
      bootstrap: true,
    },
    confusionMatrix: {
      truePositives: 450,
      falsePositives: 70,
      trueNegatives: 520,
      falseNegatives: 80,
    },
    dataset: "TensorFlow Core Dataset",
    datasetId: "dataset-1",
  },
  {
    id: "model-2",
    name: "React Component Defect Detector",
    repository: "facebook/react",
    repositoryId: "pub-2",
    type: "XGBoost",
    accuracy: 0.84,
    f1Score: 0.82,
    precision: 0.83,
    recall: 0.81,
    auc: 0.89,
    dateCreated: "2023-04-17T09:15:00Z",
    creator: "web-quality",
    description: "Detects potential defects in React components",
    features: [
      { name: "CBO", importance: 0.16 },
      { name: "RFC", importance: 0.14 },
      { name: "WMC", importance: 0.13 },
      { name: "LCOM", importance: 0.11 },
      { name: "lines_added", importance: 0.1 },
      { name: "files_changed", importance: 0.09 },
      { name: "commit_hour", importance: 0.08 },
      { name: "commit_day", importance: 0.07 },
      { name: "DIT", importance: 0.06 },
      { name: "NOC", importance: 0.05 },
    ],
    hyperparameters: {
      n_estimators: 200,
      max_depth: 8,
      learning_rate: 0.1,
      subsample: 0.8,
      colsample_bytree: 0.8,
    },
    confusionMatrix: {
      truePositives: 380,
      falsePositives: 80,
      trueNegatives: 490,
      falseNegatives: 90,
    },
    dataset: "React Core Dataset",
    datasetId: "dataset-4",
  },
]

export default function PublicModelDetailPage({ params }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState("overview")
  const { isAuthenticated } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  // Find the model by ID
  const model = publicModels.find((m) => m.id === params.id)

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleUseModel = () => {
    if (isAuthenticated) {
      router.push(`/jobs/inference?model=${params.id}`)
    } else {
      toast({
        title: "Authentication required",
        description: "Please sign in to use this model for inference",
      })
      router.push("/login")
    }
  }

  if (!model) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center">
        <h1 className="text-2xl font-bold mb-4">Model not found</h1>
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
            <Link href={`/public-repositories/${model.repositoryId}`}>
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{model.name}</h1>
            <p className="text-muted-foreground">
              <Link href={`/public-repositories/${model.repositoryId}`} className="hover:underline">
                {model.repository}
              </Link>
            </p>
          </div>
        </div>

        {!isAuthenticated && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Want to use this model for your own code?</CardTitle>
              <CardDescription>Sign in to run inference and predict defects in your code</CardDescription>
            </CardHeader>
            <CardContent className="flex justify-between items-center">
              <p className="text-muted-foreground max-w-2xl">
                Use this pre-trained model to analyze your pull requests and commits, or train your own custom model
                based on your specific needs.
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
            <TabsTrigger value="features">Feature Importance</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Model Information</CardTitle>
                  <CardDescription>{model.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-4">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Model Type:</dt>
                      <dd>
                        <Badge variant="outline">{model.type}</Badge>
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Created:</dt>
                      <dd>{formatDate(model.dateCreated)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Creator:</dt>
                      <dd>{model.creator}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Training Dataset:</dt>
                      <dd>{model.dataset}</dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Performance Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-4">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Accuracy:</dt>
                      <dd className="font-medium">{model.accuracy.toFixed(2)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">F1 Score:</dt>
                      <dd className="font-medium">{model.f1Score.toFixed(2)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Precision:</dt>
                      <dd>{model.precision.toFixed(2)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Recall:</dt>
                      <dd>{model.recall.toFixed(2)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">AUC:</dt>
                      <dd>{model.auc.toFixed(2)}</dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Hyperparameters</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {Object.entries(model.hyperparameters).map(([key, value]) => (
                    <div key={key} className="bg-muted/30 p-3 rounded-md">
                      <div className="text-sm text-muted-foreground">{key}</div>
                      <div className="font-medium">{value.toString()}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end space-x-4">
              <Button variant="outline" asChild>
                <Link href={`/public-repositories/${model.repositoryId}`}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Repository
                </Link>
              </Button>
              <Button onClick={handleUseModel}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Use This Model
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="features" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Feature Importance</CardTitle>
                <CardDescription>The relative importance of each feature in the model</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {model.features.map((feature) => (
                    <div key={feature.name} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>{feature.name}</span>
                        <span>{(feature.importance * 100).toFixed(1)}%</span>
                      </div>
                      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${feature.importance * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button onClick={handleUseModel}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Use This Model
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="performance" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Confusion Matrix</CardTitle>
                <CardDescription>Model prediction performance on test data</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 max-w-md mx-auto">
                  <div className="bg-primary/10 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">True Positives</div>
                    <div className="text-2xl font-bold">{model.confusionMatrix.truePositives}</div>
                  </div>
                  <div className="bg-muted p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">False Positives</div>
                    <div className="text-2xl font-bold">{model.confusionMatrix.falsePositives}</div>
                  </div>
                  <div className="bg-muted p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">False Negatives</div>
                    <div className="text-2xl font-bold">{model.confusionMatrix.falseNegatives}</div>
                  </div>
                  <div className="bg-primary/10 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">True Negatives</div>
                    <div className="text-2xl font-bold">{model.confusionMatrix.trueNegatives}</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
                <CardDescription>Detailed model performance metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                  <div className="bg-muted/30 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">Accuracy</div>
                    <div className="text-2xl font-bold">{model.accuracy.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">F1 Score</div>
                    <div className="text-2xl font-bold">{model.f1Score.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">Precision</div>
                    <div className="text-2xl font-bold">{model.precision.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">Recall</div>
                    <div className="text-2xl font-bold">{model.recall.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 p-4 rounded-md text-center">
                    <div className="text-sm text-muted-foreground">AUC</div>
                    <div className="text-2xl font-bold">{model.auc.toFixed(2)}</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end space-x-4">
              <Button variant="outline" asChild>
                <Link href={`/public-repositories/${model.repositoryId}`}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Repository
                </Link>
              </Button>
              <Button onClick={handleUseModel}>
                {!isAuthenticated && <Lock className="mr-2 h-4 w-4" />}
                Use This Model
              </Button>
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
