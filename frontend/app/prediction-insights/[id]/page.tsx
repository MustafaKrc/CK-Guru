"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { MainLayout } from "@/components/main-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Info, AlertTriangle, CheckCircle, HelpCircle } from "lucide-react"
import { FeatureImportanceChart } from "@/components/explainable-ai/feature-importance-chart"
import { ShapValuesChart } from "@/components/explainable-ai/shap-values-chart"
import { CounterfactualExplanation } from "@/components/explainable-ai/counterfactual-explanation"
import { DecisionPathVisualization } from "@/components/explainable-ai/decision-path-visualization"
import { WhatIfAnalysis } from "@/components/explainable-ai/what-if-analysis"
import { PageContainer } from "@/components/ui/page-container"

// Mock data for a prediction result
const mockPrediction = {
  id: "pred-123456",
  modelId: "model-1",
  modelName: "RandomForest-frontend-1",
  modelType: "RandomForest",
  timestamp: "2023-05-10T14:30:00Z",
  input: {
    commitId: "a1b2c3d4e5f6",
    repository: "frontend-app",
    branch: "feature/new-component",
    author: "jane.doe@example.com",
    files: ["src/components/Button.tsx", "src/utils/validation.ts"],
    linesAdded: 45,
    linesRemoved: 12,
    complexity: 8.2,
    codeChurn: 0.34,
    commitMessage: "Add form validation and improve button accessibility",
    timeOfDay: 14,
    dayOfWeek: 2,
    codeMetrics: {
      cyclomaticComplexity: 12,
      cognitiveComplexity: 8,
      halsteadVolume: 245.6,
      maintainabilityIndex: 68,
    },
  },
  prediction: {
    label: "defect-prone",
    probability: 0.78,
    confidence: "high",
    riskLevel: "medium",
  },
  featureImportance: [
    { feature: "cyclomaticComplexity", importance: 0.28, value: 12 },
    { feature: "linesAdded", importance: 0.22, value: 45 },
    { feature: "codeChurn", importance: 0.18, value: 0.34 },
    { feature: "cognitiveComplexity", importance: 0.15, value: 8 },
    { feature: "halsteadVolume", importance: 0.09, value: 245.6 },
    { feature: "maintainabilityIndex", importance: 0.08, value: 68 },
  ],
  shapValues: [
    { feature: "cyclomaticComplexity", value: 0.31, baseline: 0 },
    { feature: "linesAdded", value: 0.25, baseline: 0 },
    { feature: "codeChurn", value: 0.15, baseline: 0 },
    { feature: "cognitiveComplexity", value: 0.12, baseline: 0 },
    { feature: "halsteadVolume", value: -0.08, baseline: 0 },
    { feature: "maintainabilityIndex", value: -0.05, baseline: 0 },
  ],
  counterfactuals: [
    {
      feature: "cyclomaticComplexity",
      currentValue: 12,
      suggestedValue: 8,
      impact: -0.25,
    },
    {
      feature: "linesAdded",
      currentValue: 45,
      suggestedValue: 30,
      impact: -0.18,
    },
    {
      feature: "cognitiveComplexity",
      currentValue: 8,
      suggestedValue: 5,
      impact: -0.12,
    },
  ],
  decisionPath: {
    nodes: [
      { id: "0", condition: "cyclomaticComplexity > 10", samples: 1000, value: [0.6, 0.4] },
      { id: "1", condition: "linesAdded > 40", samples: 600, value: [0.3, 0.7] },
      { id: "3", condition: "codeChurn > 0.3", samples: 400, value: [0.2, 0.8] },
      { id: "7", condition: "Leaf", samples: 320, value: [0.1, 0.9] },
    ],
    edges: [
      { source: "0", target: "1", label: "True" },
      { source: "1", target: "3", label: "True" },
      { source: "3", target: "7", label: "True" },
    ],
    path: ["0", "1", "3", "7"],
  },
}

export default function PredictionInsightsPage({ params }: { params: { id: string } }) {
  const [prediction, setPrediction] = useState(mockPrediction)
  const [activeTab, setActiveTab] = useState("overview")
  const router = useRouter()

  // In a real app, fetch the prediction data based on the ID
  useEffect(() => {
    // Simulate API call
    console.log(`Fetching prediction with ID: ${params.id}`)
    // In a real app, you would fetch the data here
  }, [params.id])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString() + " " + new Date(dateString).toLocaleTimeString()
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <PageContainer
          actions={
            <Button variant="outline" size="icon" asChild>
              <Link href="/jobs/inference">
                <ArrowLeft className="h-4 w-4" />
                <span className="sr-only">Back</span>
              </Link>
            </Button>
          }
        >
          <div className="mb-6">
            <h1 className="text-3xl font-bold tracking-tight">Prediction Insights</h1>
            <p className="text-muted-foreground">
              Explainable AI for prediction <span className="font-mono">{params.id}</span>
            </p>
          </div>

          <Card>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    Prediction Result
                    {prediction.prediction.label === "defect-prone" ? (
                      <AlertTriangle className="h-5 w-5 text-warning" />
                    ) : (
                      <CheckCircle className="h-5 w-5 text-success" />
                    )}
                  </CardTitle>
                  <CardDescription>
                    Model: {prediction.modelName} | Time: {formatDate(prediction.timestamp)}
                  </CardDescription>
                </div>
                <Badge
                  className={
                    prediction.prediction.label === "defect-prone"
                      ? "bg-warning/20 text-warning hover:bg-warning/30"
                      : "bg-success/20 text-success hover:bg-success/30"
                  }
                >
                  {prediction.prediction.label === "defect-prone" ? "Defect Prone" : "Clean Code"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-muted/30 p-4 rounded-md">
                  <div className="text-sm text-muted-foreground">Probability</div>
                  <div className="text-2xl font-bold">{(prediction.prediction.probability * 100).toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground mt-1">Likelihood of the code being defect-prone</div>
                </div>
                <div className="bg-muted/30 p-4 rounded-md">
                  <div className="text-sm text-muted-foreground">Confidence</div>
                  <div className="text-2xl font-bold capitalize">{prediction.prediction.confidence}</div>
                  <div className="text-xs text-muted-foreground mt-1">Model's confidence in this prediction</div>
                </div>
                <div className="bg-muted/30 p-4 rounded-md">
                  <div className="text-sm text-muted-foreground">Risk Level</div>
                  <div className="text-2xl font-bold capitalize">{prediction.prediction.riskLevel}</div>
                  <div className="text-xs text-muted-foreground mt-1">Potential impact if defects are present</div>
                </div>
              </div>

              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
                <Info className="h-4 w-4" />
                <p>
                  This page provides insights into why the model made this prediction. Explore the tabs below to
                  understand the factors that influenced the result.
                </p>
              </div>
            </CardContent>
          </Card>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList className="grid grid-cols-2 md:grid-cols-5 gap-2">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="feature-importance">Feature Importance</TabsTrigger>
              <TabsTrigger value="shap">SHAP Values</TabsTrigger>
              <TabsTrigger value="counterfactuals">What Could Change</TabsTrigger>
              <TabsTrigger value="decision-path">Decision Path</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Input Data</CardTitle>
                    <CardDescription>The data used for this prediction</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-sm text-muted-foreground">Commit ID</div>
                          <div className="font-mono text-sm">{prediction.input.commitId.substring(0, 8)}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Repository</div>
                          <div>{prediction.input.repository}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Branch</div>
                          <div>{prediction.input.branch}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Author</div>
                          <div>{prediction.input.author}</div>
                        </div>
                      </div>

                      <div>
                        <div className="text-sm text-muted-foreground mb-1">Files Changed</div>
                        <div className="text-sm">
                          {prediction.input.files.map((file, index) => (
                            <div key={index} className="font-mono">
                              {file}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-sm text-muted-foreground">Lines Added</div>
                          <div>{prediction.input.linesAdded}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Lines Removed</div>
                          <div>{prediction.input.linesRemoved}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Complexity</div>
                          <div>{prediction.input.complexity}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground">Code Churn</div>
                          <div>{prediction.input.codeChurn}</div>
                        </div>
                      </div>

                      <div>
                        <div className="text-sm text-muted-foreground mb-1">Commit Message</div>
                        <div className="text-sm">{prediction.input.commitMessage}</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Key Factors</CardTitle>
                    <CardDescription>Top factors influencing this prediction</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <FeatureImportanceChart data={prediction.featureImportance.slice(0, 4)} compact={true} />

                    <div className="mt-6">
                      <h4 className="text-sm font-medium mb-2">What This Means</h4>
                      <p className="text-sm text-muted-foreground">
                        The model identified high cyclomatic complexity and a large number of lines added as the primary
                        risk factors. These metrics often correlate with increased defect probability.
                      </p>
                    </div>

                    <div className="mt-4 pt-4 border-t">
                      <Button variant="outline" className="w-full" onClick={() => setActiveTab("feature-importance")}>
                        <HelpCircle className="mr-2 h-4 w-4" />
                        See Detailed Explanation
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Suggested Actions</CardTitle>
                  <CardDescription>
                    Based on the model's analysis, here are some actions that could reduce the risk of defects
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {prediction.counterfactuals.map((cf, index) => (
                      <div key={index} className="flex items-start gap-4 p-4 bg-muted/30 rounded-md">
                        <div className="bg-primary/10 text-primary p-2 rounded-full">{index + 1}</div>
                        <div>
                          <h4 className="font-medium">Reduce {cf.feature}</h4>
                          <p className="text-sm text-muted-foreground mt-1">
                            Lowering {cf.feature} from {cf.currentValue} to {cf.suggestedValue} could reduce the defect
                            probability by approximately {Math.abs(cf.impact * 100).toFixed(0)}%.
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6">
                    <Button variant="outline" className="w-full" onClick={() => setActiveTab("counterfactuals")}>
                      <HelpCircle className="mr-2 h-4 w-4" />
                      Explore What-If Scenarios
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="feature-importance" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Feature Importance</CardTitle>
                  <CardDescription>How much each feature contributed to this prediction</CardDescription>
                </CardHeader>
                <CardContent>
                  <FeatureImportanceChart data={prediction.featureImportance} />

                  <div className="mt-8 space-y-6">
                    <div>
                      <h3 className="text-lg font-medium mb-2">Understanding Feature Importance</h3>
                      <p className="text-muted-foreground">
                        Feature importance shows how much each input variable influenced the model's prediction. Higher
                        values indicate a stronger influence on the outcome.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">Key Insights</h3>

                      <div className="p-4 bg-muted/30 rounded-md">
                        <h4 className="font-medium">Cyclomatic Complexity (28%)</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          This metric measures the number of independent paths through the code. Higher values indicate
                          more complex code that is harder to test and more prone to defects.
                        </p>
                      </div>

                      <div className="p-4 bg-muted/30 rounded-md">
                        <h4 className="font-medium">Lines Added (22%)</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          The number of new lines added in this commit. Larger changes tend to introduce more defects.
                        </p>
                      </div>

                      <div className="p-4 bg-muted/30 rounded-md">
                        <h4 className="font-medium">Code Churn (18%)</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          The rate at which the code changes over time. High churn often correlates with instability and
                          higher defect rates.
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="shap" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>SHAP Values</CardTitle>
                  <CardDescription>
                    SHapley Additive exPlanations show how each feature pushes the prediction up or down
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ShapValuesChart data={prediction.shapValues} />

                  <div className="mt-8 space-y-6">
                    <div>
                      <h3 className="text-lg font-medium mb-2">Understanding SHAP Values</h3>
                      <p className="text-muted-foreground">
                        SHAP values show how each feature contributes to pushing the prediction away from the baseline.
                        Positive values (red) push toward the predicted class, while negative values (blue) push away
                        from it.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">Key Insights</h3>

                      <div className="p-4 bg-muted/30 rounded-md">
                        <h4 className="font-medium">Pushing Toward "Defect-Prone"</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          Cyclomatic complexity, lines added, and code churn are all pushing the prediction toward
                          "defect-prone" classification. These are risk factors in your code.
                        </p>
                      </div>

                      <div className="p-4 bg-muted/30 rounded-md">
                        <h4 className="font-medium">Pushing Away from "Defect-Prone"</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          Maintainability index and Halstead volume are pushing slightly away from the "defect-prone"
                          classification, but their effect is smaller than the risk factors.
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="counterfactuals" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>What Could Change the Prediction</CardTitle>
                  <CardDescription>
                    Explore how changing input values could affect the prediction outcome
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <CounterfactualExplanation
                    data={prediction.counterfactuals}
                    currentProbability={prediction.prediction.probability}
                  />

                  <div className="mt-8">
                    <h3 className="text-lg font-medium mb-4">What-If Analysis</h3>
                    <p className="text-muted-foreground mb-6">
                      Adjust the values below to see how they would affect the prediction outcome.
                    </p>

                    <WhatIfAnalysis
                      features={[
                        {
                          name: "cyclomaticComplexity",
                          value: prediction.input.codeMetrics.cyclomaticComplexity,
                          min: 1,
                          max: 30,
                        },
                        { name: "linesAdded", value: prediction.input.linesAdded, min: 1, max: 100 },
                        {
                          name: "cognitiveComplexity",
                          value: prediction.input.codeMetrics.cognitiveComplexity,
                          min: 1,
                          max: 20,
                        },
                      ]}
                      currentProbability={prediction.prediction.probability}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="decision-path" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Decision Path</CardTitle>
                  <CardDescription>
                    For tree-based models, this shows the path taken through the decision tree
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <DecisionPathVisualization data={prediction.decisionPath} />

                  <div className="mt-8 space-y-6">
                    <div>
                      <h3 className="text-lg font-medium mb-2">Understanding the Decision Path</h3>
                      <p className="text-muted-foreground">
                        For tree-based models like Random Forest, this visualization shows the specific path taken
                        through the decision tree to arrive at the prediction. Each node represents a decision point.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">Path Explanation</h3>

                      <div className="space-y-2">
                        {prediction.decisionPath.nodes.map((node, index) => (
                          <div key={index} className="p-4 bg-muted/30 rounded-md">
                            <h4 className="font-medium">
                              Step {index + 1}: {node.condition}
                            </h4>
                            <p className="text-sm text-muted-foreground mt-1">
                              {node.condition !== "Leaf"
                                ? `The model checked if ${node.condition} and the answer was True.`
                                : `Final prediction: ${prediction.prediction.probability * 100}% chance of being defect-prone.`}
                            </p>
                            <div className="text-xs text-muted-foreground mt-2">
                              Based on {node.samples} similar samples from training data
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </PageContainer>
      </div>
    </MainLayout>
  )
}
