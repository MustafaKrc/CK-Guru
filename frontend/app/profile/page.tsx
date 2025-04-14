"use client"

import { useState } from "react"
import { AuthenticatedLayout } from "@/components/layout/authenticated-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ProfileSettings } from "@/components/profile/profile-settings"
import { RepositorySettings } from "@/components/profile/repository-settings"
import { IntegrationSettings } from "@/components/profile/integration-settings"
import { SecuritySettings } from "@/components/profile/security-settings"
import { NotificationSettings } from "@/components/profile/notification-settings"

export default function ProfilePage() {
  const [activeTab, setActiveTab] = useState("profile")

  return (
    <AuthenticatedLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile Settings</h1>
          <p className="text-muted-foreground">Manage your account settings, repositories, and integrations</p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid grid-cols-2 md:grid-cols-5 w-full">
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="repositories">Repositories</TabsTrigger>
            <TabsTrigger value="integrations">Integrations</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="notifications">Notifications</TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="space-y-4">
            <ProfileSettings />
          </TabsContent>

          <TabsContent value="repositories" className="space-y-4">
            <RepositorySettings />
          </TabsContent>

          <TabsContent value="integrations" className="space-y-4">
            <IntegrationSettings />
          </TabsContent>

          <TabsContent value="security" className="space-y-4">
            <SecuritySettings />
          </TabsContent>

          <TabsContent value="notifications" className="space-y-4">
            <NotificationSettings />
          </TabsContent>
        </Tabs>
      </div>
    </AuthenticatedLayout>
  )
}
