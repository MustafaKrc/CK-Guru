import type React from "react";
import { cn } from "@/lib/utils";

interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string | React.ReactNode;
  actions?: React.ReactNode;
}

export function PageContainer({
  title,
  description,
  actions,
  children,
  className,
  ...props
}: PageContainerProps) {
  return (
    <div className={cn("flex-1 space-y-4 p-4 pt-6 md:p-8", className)} {...props}>
      {/* This inner div constrains the width and centers the content */}
      <div className={cn("w-full max-w-7xl mx-auto")}>
        {(title || description || actions) && (
          <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-2 md:space-y-0 mb-6">
            {title && (
              <div className="flex-1">
                {typeof title === "string" ? (
                  <h2 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h2>
                ) : (
                  title
                )}
                {description && (
                  <div className="text-sm text-muted-foreground mt-1">{description}</div>
                )}
              </div>
            )}
            {actions && <div className="flex items-center space-x-2">{actions}</div>}
          </div>
        )}
        <div>{children}</div>
      </div>
    </div>
  );
}
