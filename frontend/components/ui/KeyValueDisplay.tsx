// frontend/components/ui/KeyValueDisplay.tsx

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "./alert"; // Assuming Alert and AlertDescription are correctly imported
import { InfoIcon } from "lucide-react"; // Assuming InfoIcon is from lucide-react
import { cn } from "@/lib/utils";

interface KeyValueDisplayProps {
  data: Record<string, any> | null | undefined;
  title: string;
  icon?: React.ReactNode;
  isLoading?: boolean;
  className?: string;
  scrollAreaMaxHeight?: string; // e.g., "max-h-[300px]"
  filterNullValues?: boolean; // Prop to control filtering
}

const KeyValueDisplay: React.FC<KeyValueDisplayProps> = ({
  data,
  title,
  icon,
  isLoading,
  className,
  scrollAreaMaxHeight = "max-h-[300px]", // Default max height for scroll area
  filterNullValues = true, // Default to true to filter out nulls
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
      <Card className={cn("flex flex-col", className)}>
        <CardHeader className="pb-3 pt-4 flex-shrink-0">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-grow overflow-hidden pt-2">
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (entriesToDisplay.length === 0) {
    return (
      <Card className={cn("flex flex-col", className)}>
        <CardHeader className="pb-3 pt-4 flex-shrink-0">
          <CardTitle className="text-base flex items-center">
            {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-grow overflow-hidden pt-2">
          <Alert variant="default" className="text-xs">
            {" "}
            {/* Ensure Alert is styled appropriately */}
            <InfoIcon className="h-3.5 w-3.5" /> {/* Ensure InfoIcon is styled */}
            <AlertDescription>No data available for display.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3 pt-4 flex-shrink-0">
        <CardTitle className="text-base flex items-center">
          {icon && <span className="mr-2 h-4 w-4 text-primary">{icon}</span>}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-grow overflow-hidden pt-2">
        {" "}
        {/* Adjusted pt-0 to pt-2 */}
        <ScrollArea className={cn("pr-3", scrollAreaMaxHeight)}>
          <dl className="space-y-2 text-sm">
            {" "}
            {/* Increased space-y for better readability of JSON */}
            {entriesToDisplay.map(([key, value]) => (
              <div
                key={key}
                // Use grid for better alignment on small screens, flex on larger
                className="grid grid-cols-1 sm:grid-cols-[auto_1fr] sm:gap-x-2 items-start border-b border-border/50 dark:border-border/30 pb-1.5 last:border-b-0"
              >
                <dt
                  className="text-muted-foreground break-words mr-2 mb-0.5 sm:mb-0 sm:text-right flex-shrink-0 text-xs sm:text-sm whitespace-nowrap"
                  title={key}
                >
                  {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}:
                </dt>
                <dd
                  className="font-mono text-left break-all w-full text-xs sm:text-sm" // Ensure dd takes full width for wrapping
                  title={
                    typeof value === "object" && value !== null
                      ? JSON.stringify(value)
                      : String(value)
                  }
                >
                  {typeof value === "object" && value !== null ? (
                    // Special handling for arrays of simple types
                    Array.isArray(value) &&
                    value.length > 0 &&
                    value.every((item) => ["string", "number", "boolean"].includes(typeof item)) &&
                    value.length <= 10 ? (
                      <div className="flex flex-wrap gap-1 justify-start pt-0.5">
                        {value.map((item, index) => (
                          <Badge
                            key={index}
                            variant="secondary"
                            className="font-normal text-xs py-0.5 px-1.5"
                          >
                            {String(item)}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      // Default formatted JSON for other objects/arrays
                      <pre className="whitespace-pre-wrap text-xs bg-muted/30 dark:bg-muted/15 p-2 rounded-sm border border-border/20 dark:border-border/10 overflow-x-auto max-w-full">
                        {JSON.stringify(value, null, 2)}
                      </pre>
                    )
                  ) : typeof value === "boolean" ? (
                    <Badge
                      variant={value ? "default" : "outline"}
                      className="text-xs py-0.5 px-1.5"
                    >
                      {value ? "True" : "False"}
                    </Badge>
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
