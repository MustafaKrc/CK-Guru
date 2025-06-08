// frontend/app/repositories/[id]/commits/[hash]/loading.tsx
import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function CommitDetailLoading() {
  return (
    <MainLayout>
      <PageContainer>
        {/* Header Skeleton */}
        <div className="flex items-center gap-4 mb-6">
            <Skeleton className="h-10 w-10" /> {/* Back button */}
            <div className="space-y-1">
                <Skeleton className="h-8 w-72" /> {/* Title */}
                <Skeleton className="h-4 w-56" />      {/* Description */}
            </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column Skeleton */}
            <div className="lg:col-span-1 space-y-6">
                <Card><CardHeader><Skeleton className="h-6 w-3/4"/></CardHeader><CardContent className="space-y-3"><Skeleton className="h-5 w-full"/><Skeleton className="h-5 w-5/6"/></CardContent></Card>
                <Card><CardHeader><Skeleton className="h-6 w-3/4"/></CardHeader><CardContent className="space-y-3"><Skeleton className="h-20 w-full"/></CardContent></Card>
            </div>
            {/* Right Column Skeleton */}
            <div className="lg:col-span-2 space-y-6">
                <Card><CardHeader><Skeleton className="h-6 w-1/3"/></CardHeader><CardContent><Skeleton className="h-16 w-full"/></CardContent></Card>
                <Card><CardHeader><Skeleton className="h-6 w-1/2"/></CardHeader><CardContent className="space-y-3"><Skeleton className="h-10 w-full"/><Skeleton className="h-10 w-full"/><Skeleton className="h-10 w-full"/></CardContent></Card>
            </div>
        </div>
      </PageContainer>
    </MainLayout>
  );
}