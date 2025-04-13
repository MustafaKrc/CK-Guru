"use client"

import type React from "react"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  BarChart3,
  Database,
  FileCode2,
  GitBranch,
  Home,
  LayoutDashboard,
  ListFilter,
  MonitorPlay,
  Settings,
  Menu,
} from "lucide-react"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"

interface MainLayoutProps {
  children: React.ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  const pathname = usePathname()
  const [isOpen, setIsOpen] = useState(false)

  const routes = [
    {
      name: "Dashboard",
      path: "/",
      icon: <Home className="h-5 w-5" />,
    },
    {
      name: "Repositories",
      path: "/repositories",
      icon: <GitBranch className="h-5 w-5" />,
    },
    {
      name: "Datasets",
      path: "/datasets",
      icon: <Database className="h-5 w-5" />,
    },
    {
      name: "Bot Patterns",
      path: "/bot-patterns",
      icon: <ListFilter className="h-5 w-5" />,
    },
    {
      name: "ML Models",
      path: "/models",
      icon: <BarChart3 className="h-5 w-5" />,
    },
    {
      name: "Model Comparison",
      path: "/model-comparison",
      icon: <FileCode2 className="h-5 w-5" />,
    },
    {
      name: "ML Jobs",
      path: "/jobs",
      icon: <MonitorPlay className="h-5 w-5" />,
    },
    {
      name: "Task Monitor",
      path: "/tasks",
      icon: <LayoutDashboard className="h-5 w-5" />,
    },
    {
      name: "Settings",
      path: "/settings",
      icon: <Settings className="h-5 w-5" />,
    },
  ]

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 flex h-16 items-center gap-4 border-b bg-background px-6 md:px-8">
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle Menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 sm:max-w-xs">
            <nav className="grid gap-2 text-lg font-medium">
              <Link href="/" className="flex items-center gap-2 text-lg font-semibold" onClick={() => setIsOpen(false)}>
                <GitBranch className="h-6 w-6 text-primary" />
                <span>CK-Guru</span>
              </Link>
              <ScrollArea className="h-[calc(100vh-8rem)] pb-10 pt-6">
                {routes.map((route) => (
                  <Link
                    key={route.path}
                    href={route.path}
                    onClick={() => setIsOpen(false)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground hover:text-foreground",
                      pathname === route.path ? "sidebar-item-active font-medium" : "",
                    )}
                  >
                    {route.icon}
                    {route.name}
                  </Link>
                ))}
              </ScrollArea>
            </nav>
          </SheetContent>
        </Sheet>
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <GitBranch className="h-6 w-6 text-primary" />
          <span>CK-Guru</span>
        </Link>
        <nav className="hidden md:flex flex-1 items-center gap-6 text-sm">
          {routes.map((route) => (
            <Link
              key={route.path}
              href={route.path}
              className={cn(
                "flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors",
                pathname === route.path ? "text-primary font-medium" : "",
              )}
            >
              {route.name}
            </Link>
          ))}
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
