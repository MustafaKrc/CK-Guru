import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"; // If tabs are used

export default function DatasetDetailLoading() {
  return (
    <MainLayout>
      <PageContainer>
        {/* Header Skeleton */}
        <div className="flex justify-between items-start mb-6">
            <div>
                <Skeleton className="h-8 w-64 mb-2" /> {/* Title */}
                <Skeleton className="h-4 w-48" />      {/* Description / Badge */}
            </div>
            <div className="flex gap-2">
                <Skeleton className="h-9 w-24" />     {/* Action Button 1 */}
                <Skeleton className="h-9 w-24" />     {/* Action Button 2 */}
            </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column Skeleton (Configuration & Models) */}
          <div className="lg:col-span-1 space-y-6">
            <Card>
              <CardHeader><Skeleton className="h-6 w-3/4 mb-1" /><Skeleton className="h-4 w-1/2" /></CardHeader>
              <CardContent className="space-y-4">
                <Skeleton className="h-5 w-1/3" /> <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-5 w-1/3" /> <Skeleton className="h-20 w-full" />
                <Skeleton className="h-5 w-1/3" /> <Skeleton className="h-20 w-full" />
              </CardContent>
              <CardFooter><Skeleton className="h-10 w-full" /></CardFooter>
            </Card>
            <Card>
              <CardHeader><Skeleton className="h-6 w-3/4 mb-1" /><Skeleton className="h-4 w-1/2" /></CardHeader>
              <CardContent><Skeleton className="h-20 w-full" /></CardContent>
            </Card>
          </div>

          {/* Right Column Skeleton (Data Preview) */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                    <div><Skeleton className="h-6 w-40 mb-1" /><Skeleton className="h-4 w-64" /></div>
                    <Skeleton className="h-9 w-48" /> {/* Download Button */}
                </div>
              </CardHeader>
              <CardContent>
                <Skeleton className="h-64 w-full mb-4" /> {/* Table Area */}
                <Skeleton className="h-10 w-1/2 mx-auto" /> {/* Pagination */}
              </CardContent>
            </Card>
          </div>
        </div>
      </PageContainer>
    </MainLayout>
  );
}