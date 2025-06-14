import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card";

export default function CreateDatasetLoading() {
  return (
    <MainLayout>
      <PageContainer>
        <div className="flex items-center gap-4 mb-6">
          <Skeleton className="h-10 w-10" /> {/* Back button */}
          <Skeleton className="h-8 w-48" /> {/* Title */}
        </div>

        {/* Stepper Skeleton */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex space-x-2">
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
          <Skeleton className="h-5 w-20" /> {/* Step X of 3 */}
        </div>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-1/4 mb-1" /> {/* Card Title */}
            <Skeleton className="h-4 w-1/2" /> {/* Card Description */}
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Skeleton className="h-4 w-1/5" /> {/* Label */}
              <Skeleton className="h-10 w-full" /> {/* Input */}
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-1/5" /> {/* Label */}
              <Skeleton className="h-10 w-full" /> {/* Input */}
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-1/5" /> {/* Label */}
              <Skeleton className="h-20 w-full" /> {/* Textarea / Larger component */}
            </div>
          </CardContent>
          <CardFooter className="flex justify-end">
            <Skeleton className="h-10 w-24" /> {/* Button */}
          </CardFooter>
        </Card>
      </PageContainer>
    </MainLayout>
  );
}
