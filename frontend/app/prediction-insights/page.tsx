"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button"; // Assuming Button is used for links
import { Skeleton } from "@/components/ui/skeleton"; // For loading state
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // For error messages
import { ExclamationTriangleIcon } from "@radix-ui/react-icons"; // For error icon

// Import dedicated API service functions and types
import { getInferenceJobs, handleApiError } from "../../../lib/apiService"; // Adjusted path
import {
  InferenceJobRead,
  PaginatedInferenceJobRead,
  JobStatusEnum,
  // FilePredictionDetail, // Not directly used here, but available from ~/types/api
  // InferenceResultPackage, // Not directly used here, but available from ~/types/api
} from "~/types/api"; // Assuming path alias is configured for frontend/types/api

// Type for the items we'll display, can be same as InferenceJobRead or a subset
type DisplayableInferenceJob = InferenceJobRead;

const PredictionInsightsPage = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [inferenceJobs, setInferenceJobs] = useState<DisplayableInferenceJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInferenceJobs = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Use the dedicated service function
        // Pass any necessary query parameters, e.g., for pagination or filtering
        const response = await getInferenceJobs({ limit: 50 }); // Example: fetch first 50
        setInferenceJobs(response.items);
      } catch (err) {
        // handleApiError now directly shows a toast, so we might not need to set error message manually
        // unless we want to display it in a specific component location.
        // For now, keeping setError for potential inline error display.
        const defaultMessage = "Failed to fetch inference jobs.";
        if (err instanceof Error) {
            setError(err.message); // Store the error message from ApiError or generic Error
        } else {
            setError(defaultMessage);
        }
        // The toast is handled by handleApiError from apiService.ts if it's called there,
        // or we can call it here if getInferenceJobs re-throws a plain error.
        // Assuming getInferenceJobs throws ApiError which is then caught by a component-level try-catch.
        // Let's adjust to call handleApiError here for UI feedback.
        handleApiError(err, "Failed to fetch jobs");

      } finally {
        setIsLoading(false);
      }
    };

    fetchInferenceJobs();
  }, []);

  const getStatusBadge = (status: JobStatusEnum) => {
    switch (status) {
      case JobStatusEnum.SUCCESS:
        return <Badge variant="success">Success</Badge>;
      case JobStatusEnum.FAILURE:
        return <Badge variant="destructive">Failure</Badge>;
      case JobStatusEnum.IN_PROGRESS:
        return <Badge variant="secondary">In Progress</Badge>;
      case JobStatusEnum.PENDING:
        return <Badge variant="outline">Pending</Badge>;
      case JobStatusEnum.CANCELLED:
        return <Badge variant="warning">Cancelled</Badge>;
      case JobStatusEnum.TIMEOUT:
        return <Badge variant="warning">Timeout</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const filteredInsights = useMemo(() => {
    if (!searchQuery) {
      return inferenceJobs;
    }
    return inferenceJobs.filter((job) => {
      const query = searchQuery.toLowerCase();
      return (
        job.id.toString().includes(query) ||
        job.ml_model_id.toString().includes(query) ||
        (job.input_reference.commit_hash && typeof job.input_reference.commit_hash === 'string' && job.input_reference.commit_hash.toLowerCase().includes(query)) ||
        (job.status && job.status.toLowerCase().includes(query))
      );
    });
  }, [searchQuery, inferenceJobs]);

  if (isLoading) {
    return (
      <div className="container mx-auto p-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Prediction Insights</h1>
          <Skeleton className="h-10 w-1/3" /> {/* Search input skeleton */}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2 mt-1" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3 mb-2" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
              <CardFooter>
                <Skeleton className="h-10 w-28" />
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-4 flex justify-center items-center h-[calc(100vh-200px)]">
        <Alert variant="destructive" className="max-w-lg">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Prediction Insights</h1>
        <Input
          type="text"
          placeholder="Search by ID, Model ID, Commit Hash, Status..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {filteredInsights.length === 0 ? (
        <div className="text-center text-gray-500 py-10">
          No inference jobs found.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredInsights.map((job) => (
            <Card key={job.id} className="flex flex-col justify-between">
              <CardHeader>
                <CardTitle>Inference Job #{job.id}</CardTitle>
                <CardDescription>
                  Model ID: {job.ml_model_id}
                  {job.input_reference.commit_hash && (
                    <span className="block text-xs text-gray-500 mt-1">
                      Commit: {String(job.input_reference.commit_hash).substring(0, 7)}...
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <strong>Status:</strong> {getStatusBadge(job.status)}
                  </div>
                  <div>
                    <strong>Created:</strong>{" "}
                    {new Date(job.created_at).toLocaleDateString()}
                  </div>
                  {job.completed_at && (
                     <div>
                       <strong>Completed:</strong>{" "}
                       {new Date(job.completed_at).toLocaleDateString()}
                     </div>
                  )}
                  <div>
                    <strong>Files Analyzed:</strong>{" "}
                    {job.prediction_result?.num_files_analyzed ?? "N/A"}
                  </div>
                   {job.status_message && (
                    <div className="text-sm text-muted-foreground">
                      <strong>Message:</strong> {job.status_message}
                    </div>
                  )}
                </div>
              </CardContent>
              <CardFooter>
                <Link href={`/prediction-insights/${job.id}`} passHref legacyBehavior>
                  <Button asChild>
                    <a>View Details</a>
                  </Button>
                </Link>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default PredictionInsightsPage;
