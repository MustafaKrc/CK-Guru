import type React from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";
import "@/app/globals.css";
import { Inter } from "next/font/google";
import type { Metadata } from "next";
import { GlobalAppEffects } from "@/components/GlobalAppEffects";

// Load Inter font with explicit configuration
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  fallback: ["system-ui", "sans-serif"],
});

export const metadata: Metadata = {
  title: "CK-Guru | Software Defect Prediction",
  description: "Just-In-Time Software Defect Prediction Platform",
  generator: "v0.dev",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          "min-h-screen bg-background font-sans antialiased",
          inter.className,
          inter.variable
        )}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            <GlobalAppEffects />
            {children}
            <Toaster />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
