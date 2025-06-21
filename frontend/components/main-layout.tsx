// frontend/components/main-layout.tsx
"use client";

import React from "react";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  BarChart3,
  Database,
  GitBranch,
  Home,
  LayoutDashboard,
  ListFilter,
  MonitorPlay,
  Settings,
  Menu,
  LogOut,
  User,
  Moon,
  Sun,
  Minimize,
  Maximize,
  ChevronDown,
  ChevronRight,
  Layers,
  Play,
  BarChart2,
  Server,
  Lightbulb,
  LineChart,
  ArrowLeft,
  Puzzle,
  Wand2,
} from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/components/auth/auth-provider";
import { useTheme } from "@/components/theme-provider";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

interface MainLayoutProps {
  children: React.ReactNode;
}

interface NavItem {
  name: string;
  path: string;
  icon: React.ReactNode;
  children?: NavItem[];
  exactPath?: boolean;
}

export function MainLayout({ children }: MainLayoutProps) {
  const pathname = usePathname();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isMobileView, setIsMobileView] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    repositories: true,
    datasets: true,
    models: true,
    jobs: true,
    insights: true,
  });
  const { user, logout, toggleDarkMode, toggleCompactView } = useAuth();
  const { theme } = useTheme();
  const [isCompact, setIsCompact] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Check if mobile view on mount and window resize
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobileView(window.innerWidth < 1024);
    };

    checkIfMobile();
    window.addEventListener("resize", checkIfMobile);

    return () => {
      window.removeEventListener("resize", checkIfMobile);
    };
  }, []);

  // Load sidebar state from localStorage on mount only once
  useEffect(() => {
    if (!isInitialized) {
      const savedState = localStorage.getItem("sidebarState");
      if (savedState) {
        try {
          const parsedState = JSON.parse(savedState);
          setOpenGroups(parsedState);
        } catch (e) {
          console.error("Failed to parse sidebar state from localStorage", e);
        }
      }
      setIsInitialized(true);
    }
  }, [isInitialized]);

  // Save sidebar state to localStorage when it changes, but only after initialization
  useEffect(() => {
    if (isInitialized && Object.keys(openGroups).length > 0) {
      localStorage.setItem("sidebarState", JSON.stringify(openGroups));
    }
  }, [openGroups, isInitialized]);

  // Set compact view based on user preferences
  useEffect(() => {
    if (user?.preferences?.compactView) {
      document.body.classList.add("compact-view");
      setIsCompact(true);
    } else {
      document.body.classList.remove("compact-view");
      setIsCompact(false);
    }
  }, [user?.preferences?.compactView]);

  // Organized navigation structure with grouping
  const navItems: NavItem[] = [
    {
      name: "Dashboard",
      path: "/dashboard",
      icon: <Home className="h-5 w-5" />,
      exactPath: true,
    },
    {
      name: "Repositories",
      path: "/repositories",
      icon: <GitBranch className="h-5 w-5" />,
      children: [
        {
          name: "All Repositories",
          path: "/repositories",
          icon: <Layers className="h-4 w-4" />,
          exactPath: true,
        },
        /*}
        {
          name: "Public Repositories",
          path: "/public-repositories",
          icon: <Server className="h-4 w-4" />,
        },
        */

        {
          name: "Bot Patterns",
          path: "/bot-patterns",
          icon: <ListFilter className="h-4 w-4" />,
        },
      ],
    },
    {
      name: "Datasets",
      path: "/datasets",
      icon: <Database className="h-5 w-5" />,
    },
    {
      name: "ML Models",
      path: "/models",
      icon: <BarChart3 className="h-5 w-5" />,
      children: [
        {
          name: "All Models",
          path: "/models",
          icon: <Layers className="h-4 w-4" />,
          exactPath: true,
        },
        {
          name: "Model Comparison",
          path: "/model-comparison",
          icon: <BarChart2 className="h-4 w-4" />,
        },
      ],
    },
    {
      name: "ML Jobs",
      path: "/jobs",
      icon: <MonitorPlay className="h-5 w-5" />,
      children: [
        {
          name: "All Jobs",
          path: "/jobs",
          icon: <Layers className="h-4 w-4" />,
          exactPath: true,
        },
        {
          name: "Training",
          path: "/jobs/train",
          icon: <Puzzle className="h-4 w-4" />,
          exactPath: true,
        },
        {
          name: "HP Search",
          path: "/jobs/hp-search",
          icon: <Wand2 className="h-4 w-4" />,
          exactPath: true,
        },
        {
          name: "Inference",
          path: "/jobs/inference",
          icon: <Play className="h-4 w-4" />,
          exactPath: true,
        },
      ],
    },
    {
      name: "Prediction Insights",
      path: "/prediction-insights",
      icon: <Lightbulb className="h-5 w-5" />,
    },
    {
      name: "Task Monitor",
      path: "/tasks",
      icon: <LayoutDashboard className="h-5 w-5" />,
    },
    {
      name: "Settings",
      path: "/profile",
      icon: <Settings className="h-5 w-5" />,
    },
  ];

  // Use useCallback to prevent recreating this function on every render
  const toggleGroup = useCallback((groupName: string) => {
    setOpenGroups((prev) => ({
      ...prev,
      [groupName]: !prev[groupName],
    }));
  }, []);

  // Generate breadcrumbs based on current path
  const generateBreadcrumbs = () => {
    if (pathname === "/dashboard") return null;

    const pathSegments = pathname.split("/").filter(Boolean);
    if (pathSegments.length === 0) return null;

    // Determine the previous path for the back button
    const previousPath =
      pathSegments.length > 1
        ? `/${pathSegments.slice(0, pathSegments.length - 1).join("/")}`
        : "/dashboard";

    return (
      <div className="flex items-center gap-2">
        {pathSegments.length > 0 && (
          <Button variant="ghost" size="icon" asChild className="mr-1 h-8 w-8">
            <Link href={previousPath}>
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
        )}
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/dashboard">Home</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />

            {pathSegments.map((segment, index) => {
              // Create the path up to this segment
              const path = `/${pathSegments.slice(0, index + 1).join("/")}`;

              // Format the segment name
              let segmentName = segment.charAt(0).toUpperCase() + segment.slice(1);
              segmentName = segmentName.replace(/-/g, " ");

              // If it's an ID (contains only alphanumeric and hyphens), format it
              if (/^[a-zA-Z0-9-]+$/.test(segment) && segment.length > 20) {
                segmentName = `${segment.substring(0, 20)}...`;
              }

              // If it's the last segment, don't make it a link
              if (index === pathSegments.length - 1) {
                return <BreadcrumbItem key={path}>{segmentName}</BreadcrumbItem>;
              }

              return (
                <React.Fragment key={path}>
                  <BreadcrumbItem>
                    <BreadcrumbLink href={path}>{segmentName}</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                </React.Fragment>
              );
            })}
          </BreadcrumbList>
        </Breadcrumb>
      </div>
    );
  };

  // Check if a path is active
  const isPathActive = (item: NavItem) => {
    if (item.exactPath) {
      return pathname === item.path;
    }
    return pathname === item.path || pathname.startsWith(item.path + "/");
  };

  // Memoize the renderNavItem function to prevent recreating it on every render
  const renderNavItem = useCallback(
    (item: NavItem, isChild = false) => {
      const isActive = isPathActive(item);
      const hasChildren = item.children && item.children.length > 0;
      const isOpen = hasChildren && openGroups[item.name.toLowerCase()];
      const anyChildActive = hasChildren && item.children?.some((child) => isPathActive(child));

      if (!hasChildren) {
        return (
          <Link
            key={item.path}
            href={item.path}
            onClick={() => isMobileView && setIsSidebarOpen(false)}
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground hover:text-foreground transition-colors",
              isActive ? "bg-primary/10 text-primary dark:bg-primary/20 font-medium" : "",
              isChild ? "pl-10 text-sm" : ""
            )}
          >
            {item.icon}
            <span>{item.name}</span>
          </Link>
        );
      }

      return (
        <div key={item.name} className="space-y-1">
          <button
            onClick={() => toggleGroup(item.name.toLowerCase())}
            className={cn(
              "flex w-full items-center justify-between rounded-lg px-3 py-2 text-muted-foreground hover:text-foreground transition-colors",
              isActive || anyChildActive ? "text-primary font-medium" : ""
            )}
          >
            <div className="flex items-center gap-2">
              {item.icon}
              <span>{item.name}</span>
            </div>
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>

          {isOpen && (
            <div className="pt-1 pl-2">
              {item.children?.map((child) => renderNavItem(child, true))}
            </div>
          )}
        </div>
      );
    },
    [pathname, openGroups, isMobileView, toggleGroup]
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar for desktop - fixed height with sticky footer */}
      <aside className="hidden lg:flex flex-col w-64 border-r bg-background h-screen">
        <div className="p-4 border-b flex-shrink-0">
          <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
            <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
            <span>JIT-Guru</span>
          </Link>
        </div>

        {/* Scrollable navigation area */}
        <div className="flex-grow overflow-auto">
          <ScrollArea className="h-full py-4">
            <nav className="grid gap-1 px-2">{navItems.map((item) => renderNavItem(item))}</nav>
          </ScrollArea>
        </div>

        {/* Fixed footer with user profile and buttons */}
        <div className="p-4 border-t flex-shrink-0">
          <div className="flex items-center gap-3 mb-4">
            <Avatar className="h-8 w-8">
              <AvatarImage src={user?.avatar || "/placeholder.svg"} alt={user?.name || "User"} />
              <AvatarFallback>{user?.name?.charAt(0) || "U"}</AvatarFallback>
            </Avatar>
            <div className="overflow-hidden">
              <p className="text-sm font-medium truncate">{user?.name}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleDarkMode}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={toggleCompactView}
              title={isCompact ? "Switch to normal view" : "Switch to compact view"}
            >
              {isCompact ? <Maximize className="h-5 w-5" /> : <Minimize className="h-5 w-5" />}
            </Button>

            <Button variant="ghost" size="icon" onClick={logout} title="Log out">
              <LogOut className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content area with scrolling */}
      <div className="flex flex-col flex-1 h-screen overflow-hidden">
        <header className="sticky top-0 z-50 flex h-16 items-center gap-4 border-b bg-background px-6 flex-shrink-0">
          <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="lg:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 sm:max-w-xs p-0">
              <div className="p-4 border-b">
                <Link
                  href="/"
                  className="flex items-center gap-2 text-lg font-semibold"
                  onClick={() => setIsSidebarOpen(false)}
                >
                  <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
                  <span>JIT-Guru</span>
                </Link>
              </div>

              <ScrollArea className="h-[calc(100vh-8rem)] py-4">
                <nav className="grid gap-1 px-2">{navItems.map((item) => renderNavItem(item))}</nav>
              </ScrollArea>
            </SheetContent>
          </Sheet>

          <Link href="/" className="flex items-center gap-2 text-lg font-semibold lg:hidden">
            <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
            <span>JIT-GURU</span>
          </Link>

          {/* Breadcrumbs in header */}
          <div className="hidden md:block flex-grow">{generateBreadcrumbs()}</div>

          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggleDarkMode} className="lg:hidden">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                  <Avatar className="h-8 w-8">
                    <AvatarImage
                      src={user?.avatar || "/placeholder.svg"}
                      alt={user?.name || "User"}
                    />
                    <AvatarFallback>{user?.name?.charAt(0) || "U"}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuItem disabled>
                  <User className="mr-2 h-4 w-4" />
                  <span>{user?.name}</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/profile">
                    <Settings className="mr-2 h-4 w-4" />
                    <span>Settings</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 p-6 overflow-auto">
          {/* Mobile breadcrumbs */}
          <div className="md:hidden mb-4">{generateBreadcrumbs()}</div>
          {children}
        </main>
      </div>
    </div>
  );
}
