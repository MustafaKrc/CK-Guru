import type React from "react";
import Image from "next/image";
import Link from "next/link";
import { GitBranch } from "lucide-react";

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <div className="flex flex-1 flex-col justify-center px-4 py-12 sm:px-6 lg:flex-none lg:px-20 xl:px-24">
        <div className="mx-auto w-full max-w-sm lg:w-96">
          <div className="mb-8">
            <Link href="/" className="flex items-center text-xl font-bold">
              <GitBranch className="h-6 w-6 text-primary mr-2" />
              <span>CK-Guru</span>
            </Link>
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">Welcome back</h2>
          </div>
          {children}
        </div>
      </div>
      <div className="relative hidden w-0 flex-1 lg:block">
        <div className="absolute inset-0 h-full w-full bg-gradient-to-br from-primary/30 to-accent/30">
          <Image
            src="/placeholder.svg?height=1080&width=1920"
            alt="Software development"
            fill
            className="object-cover mix-blend-overlay"
            priority
          />
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center p-12 text-white">
          <div className="max-w-2xl text-center">
            <h1 className="text-4xl font-bold drop-shadow-md">
              Just-In-Time Software Defect Prediction
            </h1>
            <p className="mt-4 text-xl drop-shadow-md">
              Identify potential bugs before they happen with machine learning-powered code analysis
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
