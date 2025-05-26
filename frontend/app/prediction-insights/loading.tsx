import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card } from "@/components/ui/card";

export default function PredictionInsightsListLoading() {
  return (
    <MainLayout>
      <PageContainer>
        <div className="flex justify-between items-center mb-6">
          <div>
            <Skeleton className="h-8 w-72 mb-2" /> {/* Title */}
            <Skeleton className="h-4 w-96" />      {/* Description */}
          </div>
          <Skeleton className="h-10 w-40" />     {/* Action Button */}
        </div>

        {/* Filters Skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
        
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                {Array.from({ length: 7 }).map((_, i) => (
                   <TableHead key={i}><Skeleton className="h-5 w-full" /></TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                     <TableCell key={j}><Skeleton className="h-5 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
        {/* Pagination Skeleton */}
        <div className="flex justify-center mt-6">
            <Skeleton className="h-10 w-64" />
        </div>
      </PageContainer>
    </MainLayout>
  );
}