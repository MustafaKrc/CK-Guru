import React from 'react';
import { Loader2 } from 'lucide-react';
import { MainLayout } from '@/components/main-layout'; // Assuming MainLayout provides basic page structure
import { PageContainer } from '@/components/ui/page-container'; // Assuming PageContainer provides content structure

export const PageLoader: React.FC<{ message?: string }> = ({ message = "Loading page data..." }) => {
  return (
    <MainLayout>
      <PageContainer title="" description=""> {/* Empty title/desc for loader */}
        <div className="flex flex-col items-center justify-center min-h-[calc(100vh-200px)] text-muted-foreground">
          <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
          <p className="text-lg">{message}</p>
          <p className="text-sm">Please wait a moment.</p>
        </div>
      </PageContainer>
    </MainLayout>
  );
};
