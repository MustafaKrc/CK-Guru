import type React from "react"
import { cn } from "@/lib/utils"

interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
  description?: string | React.ReactNode
  actions?: React.ReactNode
}

export function PageContainer({ title, description, actions, children, className, ...props }: PageContainerProps) {
  return (
    <div className={cn("space-y-6", className)} {...props}>
      {(title || description || actions) && (
        <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
          <div>
            {title && <h1 className="text-3xl font-bold tracking-tight">{title}</h1>}
            {description && <p className="text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 mt-4 md:mt-0">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  )
}
