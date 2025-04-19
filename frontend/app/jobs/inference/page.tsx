"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/hooks/use-toast"
import { AlertTriangle, CheckCircle, ArrowRight } from "lucide-react"
import { PageContainer } from "@/components/ui/page-container"

// Mock data for inference results
const mockResults = [
  {
    id: "pred-123456",
    commitId: "a1b2c3d4e5f6",
    repository: "frontend-app",
    branch: "feature/new-component",
    timestamp: "2023-05-10T14:30:00Z",
    prediction: {
      label: "defect-prone",
      probability: 0.78,
      confidence: "high",
    },
    model: {
      id: "model-1",
      name: "RandomForest-frontend-1",
      version: "1.0.0",
    },
  },
  {
    id: "pred-789012",
    commitId: "g7h8i9j0k1l2",
    repository: "backend-api",
    branch: "fix/auth-issue",
    timestamp: "2023-05-09T11:15:00Z",
    prediction: {
      label: "clean",
      probability: 0.92,
      confidence: "high",
    },
    model: {
      id: "model-3",
      name: "RandomForest-backend-1",
      version: "1.0.0",
    },
  },
  {
    id: "pred-345678",
    commitId: "m3n4o5p6q7r8",
    repository: "frontend-app",
    branch: "feature/user-settings",
    timestamp: "2023-05-08T09:45:00Z",
    prediction: {
      label: "defect-prone",
      probability: 0.65,
      confidence: "medium",
    },
    model: {
      id: "model-2",
      name: "XGBoost-frontend-1",
      version: "1.0.0",
    },
  },
]

export default function InferencePage() {
  const [activeTab, setActiveTab] = useState("recent")
  const router = useRouter()
  const { toast } = useToast()

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleViewDetails = (resultId: string) => {
    router.push(`/prediction-insights/${resultId}`)
  }

  const handleRunNewInference = () => {
    toast({
      title: "Running new inference",
      description: "This would open a form to run a new inference in a real app",
    })
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <PageContainer
          title="Inference Results"
          actions={<Button onClick={handleRunNewInference}>Run New Inference</Button>}
        >
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList>
              <TabsTrigger value="recent">Recent Results</TabsTrigger>
              <TabsTrigger value="saved">Saved Results</TabsTrigger>
            </TabsList>

            <TabsContent value="recent" className="space-y-4">
              {mockResults.map((result) => (
                <Card key={result.id} className="overflow-hidden">
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {result.repository}/{result.branch}
                          {result.prediction.label === "defect-prone" ? (
                            <AlertTriangle className="h-5 w-5 text-warning" />
                          ) : (
                            <CheckCircle className="h-5 w-5 text-success" />
                          )}
                        </CardTitle>
                        <CardDescription>
                          Commit: {result.commitId.substring(0, 8)} | {formatDate(result.timestamp)}
                        </CardDescription>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium">
                          {result.prediction.label === "defect-prone" ? "Defect Prone" : "Clean Code"}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {(result.prediction.probability * 100).toFixed(0)}% probability
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="pb-3">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <Label className="text-xs text-muted-foreground">Model</Label>
                        <div className="text-sm font-medium">{result.model.name}</div>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Version</Label>
                        <div className="text-sm font-medium">{result.model.version}</div>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Confidence</Label>
                        <div className="text-sm font-medium capitalize">{result.prediction.confidence}</div>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Result ID</Label>
                        <div className="text-sm font-mono">{result.id}</div>
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter className="bg-muted/30 flex justify-between items-center py-3">
                    <div className="text-sm text-muted-foreground">
                      {result.prediction.label === "defect-prone"
                        ? "This code may contain defects. View details to understand why."
                        : "This code looks good. View details to understand why."}
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => handleViewDetails(result.id)}>
                      View Details
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </TabsContent>

            <TabsContent value="saved" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>No Saved Results</CardTitle>
                  <CardDescription>
                    You haven't saved any inference results yet. You can save results from the details page.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">
                    Saved results allow you to keep track of important predictions and compare them over time.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </PageContainer>
      </div>
    </MainLayout>
  )
}
