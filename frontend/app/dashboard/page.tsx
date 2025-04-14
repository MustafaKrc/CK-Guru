"use client"

import { AuthenticatedLayout } from "@/components/layout/authenticated-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BarChart3, Database, GitBranch } from "lucide-react"
import { useAuth } from "@/components/auth/auth-provider"
import Link from "next/link"

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <AuthenticatedLayout>
      <div className="container mx-auto py-6 space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Welcome, {user?.name}</h1>
            <p className="text-muted-foreground">Here's an overview of your software defect prediction projects</p>
          </div>
          <Button asChild>
            <Link href="/repositories">View All Repositories</Link>
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card className="metric-card border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Repositories</CardTitle>
              <GitBranch className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">12</div>
              <p className="text-xs text-muted-foreground">3 repositories currently ingesting</p>
            </CardContent>
          </Card>
          <Card className="metric-card-alt border-accent/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Datasets</CardTitle>
              <Database className="h-4 w-4 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">24</div>
              <p className="text-xs text-muted-foreground">18 ready, 4 generating, 2 failed</p>
            </CardContent>
          </Card>
          <Card className="metric-card border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">ML Models</CardTitle>
              <BarChart3 className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">8</div>
              <p className="text-xs text-muted-foreground">Average F1 score: 0.82</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Recent Repositories</CardTitle>
              <CardDescription>Your most recently added repositories</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { name: "frontend-app", status: "Ingested", date: "2 days ago" },
                  { name: "backend-api", status: "Ingesting", date: "3 days ago" },
                  { name: "mobile-client", status: "Not Ingested", date: "5 days ago" },
                ].map((repo) => (
                  <div key={repo.name} className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">{repo.name}</p>
                      <p className="text-sm text-muted-foreground">{repo.date}</p>
                    </div>
                    <Badge
                      variant={
                        repo.status === "Ingested" ? "default" : repo.status === "Ingesting" ? "outline" : "secondary"
                      }
                      className={
                        repo.status === "Ingested"
                          ? "status-badge-ready"
                          : repo.status === "Ingesting"
                            ? "status-badge-running"
                            : ""
                      }
                    >
                      {repo.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Recent Jobs</CardTitle>
              <CardDescription>Your most recent ML jobs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { name: "Train RandomForest", type: "Training", status: "Completed", date: "1 day ago" },
                  { name: "HP Search XGBoost", type: "HP Search", status: "Running", date: "2 days ago" },
                  { name: "Inference on PR #123", type: "Inference", status: "Failed", date: "3 days ago" },
                ].map((job) => (
                  <div key={job.name} className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">{job.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {job.type} • {job.date}
                      </p>
                    </div>
                    <Badge
                      variant={
                        job.status === "Completed" ? "default" : job.status === "Running" ? "outline" : "destructive"
                      }
                      className={
                        job.status === "Completed"
                          ? "status-badge-ready"
                          : job.status === "Running"
                            ? "status-badge-running"
                            : "status-badge-failed"
                      }
                    >
                      {job.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AuthenticatedLayout>
  )
}
