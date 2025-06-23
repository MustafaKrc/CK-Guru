// frontend/components/ui/KeyValueDisplay.tsx

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "./alert";
import { InfoIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// --- Recursive Renderer for Nested Data ---
const ValueRenderer: React.FC<{ data: any }> = ({ data }) => {
  // Handle booleans first
  if (typeof data === "boolean") {
    return (
      <Badge variant={data ? "default" : "outline"} className="text-xs py-0.5 px-1.5">
        {data ? "True" : "False"}
      </Badge>
    );
  }

  // Handle null, undefined, and other primitives
  if (data === null || data === undefined || typeof data !== "object") {
    return (
      <span className={cn(data === null && "italic text-muted-foreground")}>
        {String(data ?? "null")}
      </span>
    );
  }

  // Handle arrays of simple primitives (render as badges)
  if (
    Array.isArray(data) &&
    data.every((item) => typeof item !== "object" || item === null) &&
    data.length <= 25 // Only for reasonably sized arrays
  ) {
    return (
      // MODIFIED: Increased max-height for simple array container
      <div className="max-h-30 overflow-auto rounded-md bg-muted/30 dark:bg-muted/15 p-2 flex flex-wrap gap-1 justify-start border border-border/20">
        {data.map((item, index) => (
          <Badge key={index} variant="secondary" className="font-normal">
            {String(item ?? "null")}
          </Badge>
        ))}
      </div>
    );
  }

  // Handle objects and complex/long arrays (render as a nested, scrollable list)
  return (
    // MODIFIED: Increased max-height for object/complex array container
    <div className="max-h-60 overflow-auto rounded-md bg-muted/30 dark:bg-muted/15 p-2 border border-border/20">
      <dl className="space-y-1.5">
        {Object.entries(data).map(([key, value]) => (
          <div
            key={key}
            className="grid grid-cols-[auto_1fr] items-start gap-x-2 border-b border-border/20 pb-1 last:border-b-0"
          >
            <dt className="text-xs text-muted-foreground whitespace-nowrap pt-px">
              {Array.isArray(data) ? `[${key}]` : `"${key}"`}:
            </dt>
            <dd className="text-xs">
              <ValueRenderer data={value} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
};

// --- Main KeyValueDisplay Component ---
interface KeyValueDisplayProps {
  data: Record<string, any> | null | undefined;
  title: string;
  icon?: React.ReactNode;
  isLoading?: boolean;
  className?: string;
  scrollAreaMaxHeight?: string;
  filterNullValues?: boolean;
}

const KeyValueDisplay: React.FC<KeyValueDisplayProps> = ({
  data,
  title,
  icon,
  isLoading,
  className,
  scrollAreaMaxHeight = "max-h-[400px]",
  filterNullValues = true,
}) => {
  const entriesToDisplay = React.useMemo(() => {
    if (!data) return [];
    let entries = Object.entries(data);
    if (filterNullValues) {
      entries = entries.filter(([_, value]) => value !== null && value !== undefined);
    }
    return entries;
  }, [data, filterNullValues]);

  if (isLoading) {
    return (
      <Card className={cn(className)}>
        <CardHeader className="pb-3 pt-4">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (entriesToDisplay.length === 0) {
    return (
      <Card className={cn(className)}>
        <CardHeader className="pb-3 pt-4">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <Alert variant="default" className="text-xs">
            <InfoIcon className="h-3.5 w-3.5" />
            <AlertDescription>No data available for display.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-3 pt-4">
        <CardTitle className="text-base flex items-center">
          {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <ScrollArea className={cn("pr-3", scrollAreaMaxHeight)}>
          <dl className="space-y-2 text-sm">
            {entriesToDisplay.map(([key, value]) => (
              <div
                key={key}
                className="grid grid-cols-1 sm:grid-cols-[auto_1fr] sm:gap-x-2 items-start border-b border-border/50 dark:border-border/30 pb-1.5 last:border-b-0"
              >
                <dt
                  className="text-muted-foreground break-words mr-2 mb-0.5 sm:mb-0 sm:text-right flex-shrink-0 text-xs sm:text-sm whitespace-nowrap pt-px"
                  title={key}
                >
                  {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}:
                </dt>
                <dd className="font-mono text-left break-all w-full text-xs sm:text-sm">
                  <ValueRenderer data={value} />
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