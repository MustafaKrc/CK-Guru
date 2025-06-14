import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export default function JobDetailLoading() {
  return (
    <MainLayout>
      <PageContainer>
        {/* Header Skeleton */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <Skeleton className="h-8 w-72 mb-2" /> {/* Title */}
            <Skeleton className="h-4 w-56" /> {/* Description / ID + Badge */}
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24" /> {/* Refresh Button */}
            <Skeleton className="h-9 w-28" /> {/* Revoke Button */}
          </div>
        </div>

        {/* Progress Bar Skeleton */}
        <div className="mb-4">
          <Skeleton className="h-3 w-1/4 mb-1" /> {/* Label */}
          <Skeleton className="h-2 w-full" /> {/* Progress */}
        </div>

        {/* Alert Skeleton (if error state is possible) */}
        {/* <Skeleton className="h-12 w-full mb-4" /> */}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Column 1: Overview & Source */}
          <div className="md:col-span-1 space-y-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
              </CardHeader>
              <CardContent className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i}>
                    <Skeleton className="h-4 w-1/3 mb-1" />
                    <Skeleton className="h-4 w-2/3" />
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-6 w-1/2" />
              </CardContent>
            </Card>
          </div>

          {/* Column 2: Configuration Details */}
          <div className="md:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-40 w-full" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-24 w-full" />
              </CardContent>
            </Card>
          </div>
        </div>
      </PageContainer>
    </MainLayout>
  );
}
