import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardContent } from "@/components/ui/card";

export default function DashboardLoading() {
  return (
    <MainLayout>
      {" "}
      {/* Or AuthenticatedLayout if needed */}
      <PageContainer>
        <div className="flex items-center justify-between mb-6">
          <div>
            <Skeleton className="h-8 w-64 mb-2" /> {/* Welcome message */}
            <Skeleton className="h-4 w-80" /> {/* Description */}
          </div>
          <Skeleton className="h-10 w-40" /> {/* Action Button */}
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <Skeleton className="h-5 w-2/3" /> {/* CardTitle */}
                <Skeleton className="h-4 w-4" /> {/* Icon */}
              </CardHeader>
              <CardContent>
                <Skeleton className="h-7 w-1/3 mb-1" /> {/* Metric value */}
                <Skeleton className="h-4 w-3/4" /> {/* Metric description */}
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-1/2" />
            </CardHeader>
            <CardContent className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-1/2" />
            </CardHeader>
            <CardContent className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </CardContent>
          </Card>
        </div>
      </PageContainer>
    </MainLayout>
  );
}
