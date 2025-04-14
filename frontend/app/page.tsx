"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { GitBranch, BarChart3, Database, GitMerge, ArrowRight, Moon, Sun, Minimize, Maximize } from "lucide-react"
import { useTheme } from "@/components/theme-provider"

export default function LandingPage() {
  const { isAuthenticated } = useAuth()
  const router = useRouter()
  const { theme, setTheme } = useTheme()
  const [isCompact, setIsCompact] = useState(false)
  const [isMounted, setIsMounted] = useState(false) // Add isMounted state

  // Initialize compact view from localStorage and set mounted state
  useEffect(() => {
    setIsMounted(true) // Set mounted to true after initial render
    const storedCompactView = localStorage.getItem("ck-guru-compact-view")
    if (storedCompactView === "true") {
      document.body.classList.add("compact-view")
      setIsCompact(true)
    }
  }, [])

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard")
    }
  }, [isAuthenticated, router])

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  const toggleCompactView = () => {
    const newCompactView = !isCompact
    setIsCompact(newCompactView)

    if (newCompactView) {
      document.body.classList.add("compact-view")
      localStorage.setItem("ck-guru-compact-view", "true")
    } else {
      document.body.classList.remove("compact-view")
      localStorage.setItem("ck-guru-compact-view", "false")
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 flex h-16 items-center gap-4 border-b bg-background px-6 md:px-8">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <GitBranch className="h-6 w-6 text-primary" />
          <span>CK-Guru</span>
        </Link>
        <nav className="hidden md:flex flex-1 items-center gap-6 text-sm">
          <Link href="#features" className="text-muted-foreground hover:text-foreground transition-colors">
            Features
          </Link>
          <Link href="#how-it-works" className="text-muted-foreground hover:text-foreground transition-colors">
            How It Works
          </Link>
          <Link href="/public-repositories" className="text-muted-foreground hover:text-foreground transition-colors">
            Public Repositories
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            className="mr-1"
            // Title can also cause mismatch if theme isn't mounted yet
            title={isMounted ? (theme === "dark" ? "Switch to light mode" : "Switch to dark mode") : "Toggle theme"}
          >
            {/* Conditionally render icon based on isMounted */}
            {isMounted ? (
              theme === "dark" ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )
            ) : (
              // Render a placeholder or default icon during SSR/initial client render
              <Moon className="h-5 w-5" /> // Or Sun, or a neutral icon
            )}
            <span className="sr-only">Toggle theme</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleCompactView}
            className="mr-2"
            title={isCompact ? "Switch to normal view" : "Switch to compact view"}
          >
            {isCompact ? <Maximize className="h-5 w-5" /> : <Minimize className="h-5 w-5" />}
            <span className="sr-only">Toggle compact view</span>
          </Button>

          <Button variant="ghost" asChild>
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">Sign up</Link>
          </Button>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden bg-gradient-to-b from-background to-muted/30 py-20 md:py-32">
          <div className="container mx-auto px-4 relative z-10">
            <div className="grid gap-8 md:grid-cols-2 items-center">
              <div className="space-y-6">
                <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
                  Predict Software Defects <span className="text-primary">Before They Happen</span>
                </h1>
                <p className="text-xl text-muted-foreground">
                  CK-Guru uses machine learning to analyze your code and predict potential bugs, helping you build more
                  reliable software.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                  <Button size="lg" asChild>
                    <Link href="/register">
                      Get Started
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" asChild>
                    <Link href="/public-repositories">Explore Public Models</Link>
                  </Button>
                </div>
              </div>
              <div className="relative h-[300px] md:h-[400px] rounded-lg overflow-hidden border bg-card shadow-xl">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-accent/10">
                  <Image
                    src="/placeholder.svg?height=800&width=1200"
                    alt="Dashboard preview"
                    fill
                    className="object-cover mix-blend-overlay"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="py-20 bg-background">
          <div className="container mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-4">Key Features</h2>
              <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                CK-Guru provides powerful tools to help you identify and prevent software defects
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                  <GitBranch className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">Repository Analysis</h3>
                <p className="text-muted-foreground">
                  Connect your Git repositories and analyze code metrics to identify potential issues
                </p>
              </div>

              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <div className="h-12 w-12 rounded-full bg-accent/10 flex items-center justify-center mb-4">
                  <Database className="h-6 w-6 text-accent" />
                </div>
                <h3 className="text-xl font-semibold mb-2">Custom Datasets</h3>
                <p className="text-muted-foreground">
                  Create and manage custom datasets with flexible cleaning rules and feature selection
                </p>
              </div>

              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                  <BarChart3 className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">ML Model Training</h3>
                <p className="text-muted-foreground">
                  Train and compare multiple machine learning models to find the best predictor for your codebase
                </p>
              </div>

              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <div className="h-12 w-12 rounded-full bg-accent/10 flex items-center justify-center mb-4">
                  <GitMerge className="h-6 w-6 text-accent" />
                </div>
                <h3 className="text-xl font-semibold mb-2">Real-time Inference</h3>
                <p className="text-muted-foreground">
                  Run inference on pull requests and commits to catch potential bugs before they're merged
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section id="how-it-works" className="py-20 bg-muted/30">
          <div className="container mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-4">How It Works</h2>
              <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                CK-Guru uses a simple four-step process to help you predict and prevent software defects
              </p>
            </div>

            <div className="grid md:grid-cols-4 gap-8">
              <div className="text-center">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <span className="text-xl font-bold text-primary">1</span>
                </div>
                <h3 className="text-xl font-semibold mb-2">Connect Repository</h3>
                <p className="text-muted-foreground">Link your Git repository to CK-Guru for analysis</p>
              </div>

              <div className="text-center">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <span className="text-xl font-bold text-primary">2</span>
                </div>
                <h3 className="text-xl font-semibold mb-2">Generate Dataset</h3>
                <p className="text-muted-foreground">Extract code metrics and create a training dataset</p>
              </div>

              <div className="text-center">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <span className="text-xl font-bold text-primary">3</span>
                </div>
                <h3 className="text-xl font-semibold mb-2">Train Models</h3>
                <p className="text-muted-foreground">Train ML models to predict defects in your codebase</p>
              </div>

              <div className="text-center">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <span className="text-xl font-bold text-primary">4</span>
                </div>
                <h3 className="text-xl font-semibold mb-2">Predict Defects</h3>
                <p className="text-muted-foreground">Run inference on new code to identify potential issues</p>
              </div>
            </div>
          </div>
        </section>

        {/* Public Repositories Section */}
        <section className="py-20 bg-background border-y">
          <div className="container mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-4">Public Repositories</h2>
              <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                Explore public repositories with pre-trained defect prediction models
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <h3 className="text-xl font-semibold mb-2">tensorflow/tensorflow</h3>
                <p className="text-muted-foreground mb-4">An open source machine learning framework for everyone</p>
                <div className="flex justify-between text-sm text-muted-foreground mb-4">
                  <span>12 models available</span>
                  <span>C++</span>
                </div>
                <Button variant="outline" className="w-full" asChild>
                  <Link href="/public-repositories/pub-1">View Repository</Link>
                </Button>
              </div>

              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <h3 className="text-xl font-semibold mb-2">facebook/react</h3>
                <p className="text-muted-foreground mb-4">
                  A declarative, efficient, and flexible JavaScript library for building user interfaces
                </p>
                <div className="flex justify-between text-sm text-muted-foreground mb-4">
                  <span>8 models available</span>
                  <span>JavaScript</span>
                </div>
                <Button variant="outline" className="w-full" asChild>
                  <Link href="/public-repositories/pub-2">View Repository</Link>
                </Button>
              </div>

              <div className="bg-card border rounded-lg p-6 shadow-sm">
                <h3 className="text-xl font-semibold mb-2">microsoft/vscode</h3>
                <p className="text-muted-foreground mb-4">Visual Studio Code</p>
                <div className="flex justify-between text-sm text-muted-foreground mb-4">
                  <span>15 models available</span>
                  <span>TypeScript</span>
                </div>
                <Button variant="outline" className="w-full" asChild>
                  <Link href="/public-repositories/pub-3">View Repository</Link>
                </Button>
              </div>
            </div>

            <div className="text-center mt-8">
              <Button asChild>
                <Link href="/public-repositories">
                  View All Public Repositories
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-20 bg-primary/5 border-y">
          <div className="container mx-auto px-4 text-center">
            <h2 className="text-3xl font-bold mb-4">Ready to improve your code quality?</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
              Join thousands of developers who use CK-Guru to build more reliable software
            </p>
            <Button size="lg" asChild>
              <Link href="/register">Get Started for Free</Link>
            </Button>
          </div>
        </section>
      </main>

      <footer className="bg-muted/30 py-12 border-t">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <Link href="/" className="flex items-center gap-2 text-lg font-semibold mb-4">
                <GitBranch className="h-6 w-6 text-primary" />
                <span>CK-Guru</span>
              </Link>
              <p className="text-muted-foreground">
                Just-In-Time Software Defect Prediction Platform powered by machine learning
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Product</h3>
              <ul className="space-y-2">
                <li>
                  <Link href="#features" className="text-muted-foreground hover:text-foreground">
                    Features
                  </Link>
                </li>
                <li>
                  <Link href="#how-it-works" className="text-muted-foreground hover:text-foreground">
                    How It Works
                  </Link>
                </li>
                <li>
                  <Link href="/public-repositories" className="text-muted-foreground hover:text-foreground">
                    Public Repositories
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Resources</h3>
              <ul className="space-y-2">
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    Documentation
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    API Reference
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    Blog
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Company</h3>
              <ul className="space-y-2">
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    About
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    Contact
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-foreground">
                    Privacy Policy
                  </Link>
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t text-center text-muted-foreground">
            <p>&copy; {new Date().getFullYear()} CK-Guru. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
