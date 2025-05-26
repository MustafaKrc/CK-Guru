"use client"

import type React from "react"

import { useState, Suspense } from "react"  
import { useRouter, useSearchParams } from "next/navigation"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Separator } from "@/components/ui/separator"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ArrowLeft, ArrowRight, HelpCircle, Info } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { PageLoader } from '@/components/ui/page-loader'; // Added import

// Mock repositories for selection
const mockRepositories = [
  { id: "1", name: "frontend-app" },
  { id: "2", name: "backend-api" },
  { id: "3", name: "mobile-client" },
  { id: "4", name: "shared-lib" },
]

// Mock available metrics
const availableMetrics = [
  { id: "CBO", name: "CBO", description: "Coupling Between Objects" },
  { id: "RFC", name: "RFC", description: "Response For a Class" },
  { id: "WMC", name: "WMC", description: "Weighted Methods per Class" },
  { id: "LCOM", name: "LCOM", description: "Lack of Cohesion of Methods" },
  { id: "DIT", name: "DIT", description: "Depth of Inheritance Tree" },
  { id: "NOC", name: "NOC", description: "Number of Children" },
  { id: "lines_added", name: "Lines Added", description: "Number of lines added in the commit" },
  { id: "lines_deleted", name: "Lines Deleted", description: "Number of lines deleted in the commit" },
  { id: "files_changed", name: "Files Changed", description: "Number of files changed in the commit" },
  { id: "commit_message_length", name: "Commit Message Length", description: "Length of the commit message" },
  { id: "commit_hour", name: "Commit Hour", description: "Hour of the day when the commit was made" },
  { id: "commit_day", name: "Commit Day", description: "Day of the week when the commit was made" },
]

// Mock available target columns
const availableTargets = [
  { id: "is_buggy", name: "Is Buggy", description: "Whether the commit introduced a bug" },
  { id: "bug_count", name: "Bug Count", description: "Number of bugs introduced by the commit" },
  { id: "bug_severity", name: "Bug Severity", description: "Severity of bugs introduced by the commit" },
]

// Mock cleaning rules
const cleaningRules = [
  {
    id: "remove_outliers",
    name: "Remove Outliers",
    description: "Identify and remove outliers from the dataset",
    enabled: true,
    parameters: [
      {
        id: "method",
        name: "Method",
        type: "select",
        options: ["iqr", "z-score", "percentile"],
        default: "iqr",
        description: "Method used to identify outliers",
      },
      {
        id: "threshold",
        name: "Threshold",
        type: "number",
        default: 1.5,
        description: "Threshold value for outlier detection",
      },
    ],
  },
  {
    id: "handle_missing_values",
    name: "Handle Missing Values",
    description: "Strategy for handling missing values in the dataset",
    enabled: true,
    parameters: [
      {
        id: "method",
        name: "Method",
        type: "select",
        options: ["mean", "median", "mode", "drop"],
        default: "mean",
        description: "Method used to handle missing values",
      },
    ],
  },
  {
    id: "filter_bot_commits",
    name: "Filter Bot Commits",
    description: "Remove commits made by bots based on patterns",
    enabled: true,
    parameters: [
      {
        id: "use_global_patterns",
        name: "Use Global Patterns",
        type: "checkbox",
        default: true,
        description: "Use global bot patterns defined in the system",
      },
      {
        id: "use_repo_patterns",
        name: "Use Repository Patterns",
        type: "checkbox",
        default: true,
        description: "Use repository-specific bot patterns",
      },
    ],
  },
  {
    id: "normalize_features",
    name: "Normalize Features",
    description: "Normalize feature values to a standard range",
    enabled: false,
    parameters: [
      {
        id: "method",
        name: "Method",
        type: "select",
        options: ["min-max", "z-score", "robust"],
        default: "min-max",
        description: "Method used for normalization",
      },
    ],
  },
]

function CreateDatasetPageContent() {  
  const router = useRouter()
  const searchParams = useSearchParams()
  const preselectedRepoId = searchParams.get("repository")

  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    repositoryId: preselectedRepoId || "",
    name: "",
    description: "",
    selectedMetrics: availableMetrics.slice(0, 6).map((m) => m.id), // Default to first 6 metrics
    targetColumn: "is_buggy",
    cleaningRules: cleaningRules.map((rule) => ({
      ...rule,
      parameters: rule.parameters.map((param) => ({
        ...param,
        value: param.default,
      })),
    })),
  })

  const { toast } = useToast()

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleMetricToggle = (metricId: string) => {
    setFormData((prev) => {
      const selectedMetrics = [...prev.selectedMetrics]
      if (selectedMetrics.includes(metricId)) {
        return { ...prev, selectedMetrics: selectedMetrics.filter((id) => id !== metricId) }
      } else {
        return { ...prev, selectedMetrics: [...selectedMetrics, metricId] }
      }
    })
  }

  const handleRuleToggle = (ruleId: string, enabled: boolean) => {
    setFormData((prev) => {
      const updatedRules = prev.cleaningRules.map((rule) => (rule.id === ruleId ? { ...rule, enabled } : rule))
      return { ...prev, cleaningRules: updatedRules }
    })
  }

  const handleParameterChange = (ruleId: string, paramId: string, value: any) => {
    setFormData((prev) => {
      const updatedRules = prev.cleaningRules.map((rule) => {
        if (rule.id === ruleId) {
          const updatedParameters = rule.parameters.map((param) => (param.id === paramId ? { ...param, value } : param))
          return { ...rule, parameters: updatedParameters }
        }
        return rule
      })
      return { ...prev, cleaningRules: updatedRules }
    })
  }

  const handleNextStep = () => {
    if (step === 1) {
      // Validate step 1
      if (!formData.repositoryId || !formData.name) {
        toast({
          title: "Missing information",
          description: "Please select a repository and provide a dataset name",
          variant: "destructive",
        })
        return
      }
    } else if (step === 2) {
      // Validate step 2
      if (formData.selectedMetrics.length === 0) {
        toast({
          title: "No features selected",
          description: "Please select at least one feature for your dataset",
          variant: "destructive",
        })
        return
      }
    }

    setStep((prev) => prev + 1)
  }

  const handlePreviousStep = () => {
    setStep((prev) => prev - 1)
  }

  const handleSubmit = () => {
    // In a real app, this would be an API call to create the dataset
    console.log("Creating dataset with data:", formData)

    toast({
      title: "Dataset creation started",
      description: "Your dataset is being generated. You'll be notified when it's ready.",
    })

    // Redirect to datasets page
    router.push("/datasets")
  }

  const getSelectedRepository = () => {
    return mockRepositories.find((repo) => repo.id === formData.repositoryId)
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
            <span className="sr-only">Back</span>
          </Button>
          <h1 className="text-3xl font-bold tracking-tight">Create Dataset</h1>
        </div>

        <div className="flex justify-between items-center">
          <div className="flex space-x-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full ${step >= 1 ? "bg-primary text-primary-foreground" : "border"}`}
            >
              1
            </div>
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full ${step >= 2 ? "bg-primary text-primary-foreground" : "border"}`}
            >
              2
            </div>
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full ${step >= 3 ? "bg-primary text-primary-foreground" : "border"}`}
            >
              3
            </div>
          </div>
          <div className="text-sm text-muted-foreground">Step {step} of 3</div>
        </div>

        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Select a repository and provide basic information for your dataset</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="repositoryId">Repository</Label>
                <select
                  id="repositoryId"
                  name="repositoryId"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={formData.repositoryId}
                  onChange={handleInputChange}
                >
                  <option value="">Select a repository</option>
                  {mockRepositories.map((repo) => (
                    <option key={repo.id} value={repo.id}>
                      {repo.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Dataset Name</Label>
                <Input
                  id="name"
                  name="name"
                  placeholder="e.g., frontend-app-dataset-1"
                  value={formData.name}
                  onChange={handleInputChange}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  name="description"
                  placeholder="Describe the purpose and contents of this dataset"
                  value={formData.description}
                  onChange={handleInputChange}
                  rows={3}
                />
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleNextStep}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Feature Selection</CardTitle>
              <CardDescription>Select the features to include in your dataset and the target column</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium">Features</h3>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setFormData((prev) => ({
                        ...prev,
                        selectedMetrics:
                          prev.selectedMetrics.length === availableMetrics.length
                            ? []
                            : availableMetrics.map((m) => m.id),
                      }))
                    }
                  >
                    {formData.selectedMetrics.length === availableMetrics.length ? "Deselect All" : "Select All"}
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {availableMetrics.map((metric) => (
                    <div key={metric.id} className="flex items-start space-x-2">
                      <Checkbox
                        id={`metric-${metric.id}`}
                        checked={formData.selectedMetrics.includes(metric.id)}
                        onCheckedChange={() => handleMetricToggle(metric.id)}
                      />
                      <div className="grid gap-1.5 leading-none">
                        <label
                          htmlFor={`metric-${metric.id}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {metric.name}
                        </label>
                        <p className="text-sm text-muted-foreground">{metric.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="text-lg font-medium">Target Column</h3>
                <div className="space-y-2">
                  <Label htmlFor="targetColumn">Select Target</Label>
                  <select
                    id="targetColumn"
                    name="targetColumn"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    value={formData.targetColumn}
                    onChange={handleInputChange}
                  >
                    {availableTargets.map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-sm text-muted-foreground mt-1">
                    {availableTargets.find((t) => t.id === formData.targetColumn)?.description}
                  </p>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Previous
              </Button>
              <Button onClick={handleNextStep}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>Cleaning Rules</CardTitle>
              <CardDescription>Configure data cleaning rules to prepare your dataset</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {formData.cleaningRules.map((rule) => (
                <div key={rule.id} className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <Checkbox
                      id={`rule-${rule.id}`}
                      checked={rule.enabled}
                      onCheckedChange={(checked) => handleRuleToggle(rule.id, checked === true)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <div className="flex items-center space-x-2">
                        <label
                          htmlFor={`rule-${rule.id}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {rule.name}
                        </label>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Info className="h-4 w-4 text-muted-foreground" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>{rule.description}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                      <p className="text-sm text-muted-foreground">{rule.description}</p>
                    </div>
                  </div>

                  {rule.enabled && rule.parameters.length > 0 && (
                    <div className="ml-7 pl-4 border-l space-y-4">
                      {rule.parameters.map((param) => (
                        <div key={param.id} className="space-y-2">
                          <div className="flex items-center space-x-2">
                            <Label htmlFor={`${rule.id}-${param.id}`} className="text-sm">
                              {param.name}
                            </Label>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <HelpCircle className="h-4 w-4 text-muted-foreground" />
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>{param.description}</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          </div>

                          {param.type === "select" && (
                            <select
                              id={`${rule.id}-${param.id}`}
                              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                              value={param.value}
                              onChange={(e) => handleParameterChange(rule.id, param.id, e.target.value)}
                            >
                              {param.options?.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}

                          {param.type === "number" && (
                            <Input
                              id={`${rule.id}-${param.id}`}
                              type="number"
                              value={param.value}
                              onChange={(e) =>
                                handleParameterChange(rule.id, param.id, Number.parseFloat(e.target.value))
                              }
                              className="h-9"
                            />
                          )}

                          {param.type === "checkbox" && (
                            <Checkbox
                              id={`${rule.id}-${param.id}`}
                              checked={param.value}
                              onCheckedChange={(checked) => handleParameterChange(rule.id, param.id, checked === true)}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  <Separator />
                </div>
              ))}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Previous
              </Button>
              <Button onClick={handleSubmit}>Create & Generate Dataset</Button>
            </CardFooter>
          </Card>
        )}
      </div>
    </MainLayout>
  )
}

export default function CreateDatasetPage() { // New wrapper component
  return (
    <Suspense fallback={<PageLoader message="Loading dataset creation form..." />}>
      <CreateDatasetPageContent />
    </Suspense>
  );
}
