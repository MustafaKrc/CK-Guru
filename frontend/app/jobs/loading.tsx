import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";

export default function JobsListLoading() {
  return (
    <MainLayout>
      <PageContainer>
        <div className="flex items-center justify-between mb-6">
          <div>
            <Skeleton className="h-8 w-56 mb-2" /> {/* Title */}
            <Skeleton className="h-4 w-72" />      {/* Description */}
          </div>
          <div className="flex space-x-2">
            <Skeleton className="h-10 w-32" /> {/* Action Button 1 */}
            <Skeleton className="h-10 w-36" /> {/* Action Button 2 */}
            <Skeleton className="h-10 w-32" /> {/* Action Button 3 */}
          </div>
        </div>

        {/* Filters Skeleton */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <Skeleton className="h-10 flex-grow" /> {/* Search */}
          <Skeleton className="h-10 w-full md:w-48" /> {/* Select Filter */}
        </div>

        <Tabs defaultValue="training" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="training"><Skeleton className="h-5 w-28" /></TabsTrigger>
            <TabsTrigger value="hpSearch"><Skeleton className="h-5 w-32" /></TabsTrigger>
            <TabsTrigger value="inference"><Skeleton className="h-5 w-28" /></TabsTrigger>
          </TabsList>

          <TabsContent value="training">
            <Card>
              <CardHeader><Skeleton className="h-6 w-40" /></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      {Array.from({ length: 6 }).map((_, i) => (
                        <TableHead key={i}><Skeleton className="h-5 w-full" /></TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: 3 }).map((_, i) => (
                      <TableRow key={i}>
                        {Array.from({ length: 6 }).map((_, j) => (
                          <TableCell key={j}><Skeleton className="h-5 w-full" /></TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <div className="flex justify-center mt-4"><Skeleton className="h-10 w-64" /></div>
              </CardContent>
            </Card>
          </TabsContent>
          {/* Add similar TabsContent for hpSearch and inference if needed */}
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}