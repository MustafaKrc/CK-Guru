// frontend/components/ui/KeyValueDisplay.tsx

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from '@/lib/utils';

interface KeyValueDisplayProps {
  data: Record<string, any> | null | undefined;
  title: string;
  icon?: React.ReactNode;
  isLoading?: boolean;
  className?: string;
  scrollAreaMaxHeight?: string;
}

const KeyValueDisplay: React.FC<KeyValueDisplayProps> = ({
  data,
  title,
  icon,
  isLoading,
  className,
  scrollAreaMaxHeight = "max-h-[300px]",
}) => {
  if (isLoading) {
    return (
      <Card className={cn("flex flex-col", className)}>
        <CardHeader className="pb-3 flex-shrink-0">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-grow overflow-hidden">
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data || Object.keys(data).length === 0) {
    return (
      <Card className={cn("flex flex-col", className)}>
        <CardHeader className="pb-3 flex-shrink-0">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-grow overflow-hidden">
          <p className="text-sm text-muted-foreground">No data available.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3 flex-shrink-0">
        <CardTitle className="text-base flex items-center">
          {icon && <span className="mr-2">{icon}</span>}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-grow overflow-hidden pt-0">
        <ScrollArea className={cn("pr-3", scrollAreaMaxHeight)}>
          <dl className="space-y-2 text-sm"> {/* Increased space-y for better readability of JSON */}
            {Object.entries(data).map(([key, value]) => (
              <div
                key={key}
                className="flex flex-col sm:flex-row sm:justify-between sm:items-start border-b border-dashed pb-1.5 last:border-b-0"
              >
                <dt className="text-muted-foreground break-words mr-2 mb-0.5 sm:mb-0 flex-shrink-0" title={key}>
                  {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}:
                </dt>
                <dd
                  className="font-mono text-left sm:text-right break-all w-full" // Ensure dd takes full width on small screens
                  title={typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}
                >
                  {typeof value === "object" && value !== null ? (
                    <pre className="whitespace-pre-wrap text-xs bg-muted/50 p-2 rounded-sm overflow-x-auto">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    String(value)
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export { KeyValueDisplay };