import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ModelComparisonLoading() {
  return (
    <MainLayout>
      <PageContainer>
        <div className="flex items-center justify-between mb-6">
          <div>
            <Skeleton className="h-8 w-64 mb-2" /> {/* Title */}
            <Skeleton className="h-4 w-80" />      {/* Description */}
          </div>
          <Skeleton className="h-10 w-36" />     {/* Export Button */}
        </div>

        <Tabs defaultValue="comparison" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="comparison"><Skeleton className="h-5 w-28" /></TabsTrigger>
            <TabsTrigger value="models"><Skeleton className="h-5 w-20" /></TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Model Selection Card Skeleton */}
        <Card className="mb-6">
          <CardHeader>
            <Skeleton className="h-6 w-40 mb-1" /> {/* Card Title */}
            <Skeleton className="h-4 w-64" />      {/* Card Description */}
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-8 w-1/2 mb-4" /> {/* Selected models display */}
            <div className="flex flex-col md:flex-row gap-4">
              <Skeleton className="h-10 w-full md:w-1/2" /> {/* Search Input */}
              <Skeleton className="h-10 w-full md:w-1/2" /> {/* Type Filter Select */}
            </div>
            <Skeleton className="h-40 w-full" /> {/* Model list scroll area */}
          </CardContent>
        </Card>

        {/* Charts Skeleton */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card className="col-span-2">
            <CardHeader>
              <Skeleton className="h-6 w-48" /> {/* Chart Title */}
            </CardHeader>
            <CardContent>
              <Skeleton className="h-10 w-40 mb-6" /> {/* Metric Select */}
              <Skeleton className="h-72 w-full" /> {/* Bar Chart Area */}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><Skeleton className="h-6 w-32" /></CardHeader>
            <CardContent className="space-y-4">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </CardContent>
          </Card>
          <Card className="col-span-3">
            <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
            <CardContent><Skeleton className="h-96 w-full" /></CardContent> {/* Radar Chart Area */}
          </Card>
        </div>
      </PageContainer>
    </MainLayout>
  );
}