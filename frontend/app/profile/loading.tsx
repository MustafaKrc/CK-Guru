import { MainLayout } from "@/components/main-layout"; 
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ProfileLoading() {
  return (
    <MainLayout> {/* Or AuthenticatedLayout */}
      <PageContainer>
        <div className="mb-6">
          <Skeleton className="h-8 w-56 mb-2" /> {/* Title */}
          <Skeleton className="h-4 w-80" />      {/* Description */}
        </div>

        <Tabs defaultValue="profile" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <TabsTrigger key={i} value={`tab-${i}`}><Skeleton className="h-5 w-24" /></TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-1/3 mb-1" />
            <Skeleton className="h-4 w-2/3" />
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col md:flex-row gap-6">
                <div className="flex flex-col items-center space-y-4">
                    <Skeleton className="h-24 w-24 rounded-full" />
                    <Skeleton className="h-9 w-32" />
                </div>
                <div className="flex-1 space-y-4">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                </div>
            </div>
            <Skeleton className="h-px w-full" /> {/* Separator */}
            <Skeleton className="h-6 w-1/4" /> {/* Sub-title */}
            <Skeleton className="h-12 w-full" /> {/* Switch + text */}
            <Skeleton className="h-12 w-full" /> {/* Switch + text */}
            <div className="flex justify-end">
                <Skeleton className="h-10 w-28" /> {/* Save Button */}
            </div>
          </CardContent>
        </Card>
      </PageContainer>
    </MainLayout>
  );
}