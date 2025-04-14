"use client"

import type React from "react"

import { createContext, useContext, useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { useTheme } from "@/components/theme-provider"

type UserPreferences = {
  darkMode: boolean
  compactView: boolean
}

type User = {
  id: string
  name: string
  email: string
  role: "admin" | "user"
  avatar?: string
  jobTitle?: string
  company?: string
  preferences?: UserPreferences
}

type AuthContextType = {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  updateUser: (updatedUser: User) => void
  isAuthenticated: boolean
  toggleDarkMode: () => void
  toggleCompactView: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const { theme, setTheme } = useTheme()
  const initialThemeSet = useRef(false)

  // Check if user is already logged in
  useEffect(() => {
    const storedUser = localStorage.getItem("ck-guru-user")
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser))
      } catch (error) {
        console.error("Failed to parse stored user:", error)
        localStorage.removeItem("ck-guru-user")
      }
    }
    setIsLoading(false)
  }, [])

  // This will sync the theme with user preferences only on initial load
  useEffect(() => {
    if (user && !initialThemeSet.current) {
      if (user.preferences?.darkMode) {
        setTheme("dark")
      } else {
        setTheme("light")
      }
      initialThemeSet.current = true
    }
  }, [user, setTheme])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    try {
      // In a real app, this would be an API call to authenticate
      // For demo purposes, we'll simulate a successful login with mock data
      if (email && password) {
        // Mock successful login
        const mockUser: User = {
          id: "user-1",
          name: email.split("@")[0],
          email,
          role: email.includes("admin") ? "admin" : "user",
          avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(email.split("@")[0])}&background=random`,
          preferences: {
            darkMode: false,
            compactView: false,
          },
        }

        // Store user in localStorage for persistence
        localStorage.setItem("ck-guru-user", JSON.stringify(mockUser))
        setUser(mockUser)
        initialThemeSet.current = false // Reset so theme will be set on login
        router.push("/dashboard")
      } else {
        throw new Error("Invalid credentials")
      }
    } catch (error) {
      console.error("Login failed:", error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const updateUser = (updatedUser: User) => {
    // Update user in state and localStorage
    setUser(updatedUser)
    localStorage.setItem("ck-guru-user", JSON.stringify(updatedUser))

    // Update theme based on user preferences
    if (updatedUser.preferences?.darkMode) {
      setTheme("dark")
    } else {
      setTheme("light")
    }
  }

  const toggleDarkMode = () => {
    if (!user) return

    const newDarkMode = !user.preferences?.darkMode
    const updatedUser = {
      ...user,
      preferences: {
        ...user.preferences,
        darkMode: newDarkMode,
      },
    }

    // Update user with new preference
    updateUser(updatedUser)
  }

  const toggleCompactView = () => {
    if (!user) return

    const newCompactView = !user.preferences?.compactView
    const updatedUser = {
      ...user,
      preferences: {
        ...user.preferences,
        compactView: newCompactView,
      },
    }

    // Update user with new preference
    updateUser(updatedUser)
  }

  const logout = () => {
    localStorage.removeItem("ck-guru-user")
    setUser(null)
    router.push("/")
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        logout,
        updateUser,
        isAuthenticated: !!user,
        toggleDarkMode,
        toggleCompactView,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
