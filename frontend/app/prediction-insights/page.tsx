"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Search, ArrowRight, Calendar, FileText, BarChart } from "lucide-react"
import Link from "next/link"

interface PredictionInsight {
  id: string
  title: string
  modelName: string
  date: string
  status: "high_confidence" | "medium_confidence" | "low_confidence"
  fileCount: number
}

export default function PredictionInsightsPage() {
  const [searchQuery, setSearchQuery] = useState("")

  // Mock data for prediction insights
  const insights: PredictionInsight[] = [
    {
      id: "insight-123",
      title: "Authentication Service Analysis",
      modelName: "CodeQuality-v2",
      date: "2023-11-15",
      status: "high_confidence",
      fileCount: 12,
    },
    {
      id: "insight-456",
      title: "Payment Gateway Integration",
      modelName: "SecurityAudit-v1",
      date: "2023-11-10",
      status: "medium_confidence",
      fileCount: 8,
    },
    {
      id: "insight-789",
      title: "User Profile Management",
      modelName: "CodeQuality-v2",
      date: "2023-11-05",
      status: "low_confidence",
      fileCount: 15,
    },
    {
      id: "insight-101",
      title: "Database Migration Scripts",
      modelName: "PerformanceOptimizer-v1",
      date: "2023-10-28",
      status: "high_confidence",
      fileCount: 5,
    },
    {
      id: "insight-102",
      title: "API Endpoint Refactoring",
      modelName: "CodeQuality-v2",
      date: "2023-10-20",
      status: "medium_confidence",
      fileCount: 23,
    },
  ]

  const filteredInsights = insights.filter(
    (insight) =>
      insight.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      insight.modelName.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "high_confidence":
        return (
          <Badge className="bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-100">
            High Confidence
          </Badge>
        )
      case "medium_confidence":
        return (
          <Badge className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-100">
            Medium Confidence
          </Badge>
        )
      case "low_confidence":
        return (
          <Badge className="bg-red-100 text-red-800 hover:bg-red-100 dark:bg-red-900 dark:text-red-100">
            Low Confidence
          </Badge>
        )
      default:
        return <Badge>{status}</Badge>
    }
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Prediction Insights</h1>
            <p className="text-muted-foreground mt-1">Explore and understand model predictions with explainable AI</p>
          </div>
          <Button asChild>
            <Link href="/jobs/inference">
              Generate New Insights
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search insights by title or model..."
            className="pl-10"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredInsights.map((insight) => (
            <Card key={insight.id} className="overflow-hidden">
              <CardHeader className="pb-2">
                <CardTitle className="text-xl">{insight.title}</CardTitle>
                <CardDescription className="flex items-center mt-1">
                  <BarChart className="h-4 w-4 mr-1" />
                  {insight.modelName}
                </CardDescription>
              </CardHeader>
              <CardContent className="pb-2">
                <div className="flex justify-between items-center mb-4">
                  <div className="flex items-center text-sm text-muted-foreground">
                    <Calendar className="h-4 w-4 mr-1" />
                    {insight.date}
                  </div>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <FileText className="h-4 w-4 mr-1" />
                    {insight.fileCount} files
                  </div>
                </div>
                <div>{getStatusBadge(insight.status)}</div>
              </CardContent>
              <CardFooter className="bg-muted/50 pt-2">
                <Button asChild variant="ghost" className="w-full">
                  <Link href={`/prediction-insights/${insight.id}`}>
                    View Details
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>

        {filteredInsights.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No insights found matching your search criteria.</p>
          </div>
        )}
      </div>
    </MainLayout>
  )
}
