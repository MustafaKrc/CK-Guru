"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Loader2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

export function NotificationSettings() {
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [notifications, setNotifications] = useState({
    email: {
      repositoryUpdates: true,
      modelTrainingComplete: true,
      inferenceResults: true,
      securityAlerts: true,
      weeklyDigest: false,
    },
    inApp: {
      repositoryUpdates: true,
      modelTrainingComplete: true,
      inferenceResults: true,
      securityAlerts: true,
    },
  })

  const handleSwitchChange = (category: "email" | "inApp", name: string, checked: boolean) => {
    setNotifications((prev) => ({
      ...prev,
      [category]: {
        ...prev[category],
        [name]: checked,
      },
    }))
  }

  const handleSaveNotifications = async () => {
    setIsLoading(true)

    try {
      // In a real app, this would be an API call
      await new Promise((resolve) => setTimeout(resolve, 1000))

      toast({
        title: "Notification settings saved",
        description: "Your notification preferences have been updated",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save notification settings",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications</CardTitle>
          <CardDescription>Configure which email notifications you receive</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-repo-updates">Repository Updates</Label>
                <p className="text-sm text-muted-foreground">
                  Receive notifications when repositories are updated or ingested
                </p>
              </div>
              <Switch
                id="email-repo-updates"
                checked={notifications.email.repositoryUpdates}
                onCheckedChange={(checked) => handleSwitchChange("email", "repositoryUpdates", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-model-training">Model Training Complete</Label>
                <p className="text-sm text-muted-foreground">
                  Receive notifications when model training jobs are completed
                </p>
              </div>
              <Switch
                id="email-model-training"
                checked={notifications.email.modelTrainingComplete}
                onCheckedChange={(checked) => handleSwitchChange("email", "modelTrainingComplete", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-inference">Inference Results</Label>
                <p className="text-sm text-muted-foreground">Receive notifications when inference jobs are completed</p>
              </div>
              <Switch
                id="email-inference"
                checked={notifications.email.inferenceResults}
                onCheckedChange={(checked) => handleSwitchChange("email", "inferenceResults", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-security">Security Alerts</Label>
                <p className="text-sm text-muted-foreground">Receive notifications about security-related events</p>
              </div>
              <Switch
                id="email-security"
                checked={notifications.email.securityAlerts}
                onCheckedChange={(checked) => handleSwitchChange("email", "securityAlerts", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-digest">Weekly Digest</Label>
                <p className="text-sm text-muted-foreground">Receive a weekly summary of activity and insights</p>
              </div>
              <Switch
                id="email-digest"
                checked={notifications.email.weeklyDigest}
                onCheckedChange={(checked) => handleSwitchChange("email", "weeklyDigest", checked)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>In-App Notifications</CardTitle>
          <CardDescription>Configure which in-app notifications you receive</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="inapp-repo-updates">Repository Updates</Label>
                <p className="text-sm text-muted-foreground">
                  Show notifications when repositories are updated or ingested
                </p>
              </div>
              <Switch
                id="inapp-repo-updates"
                checked={notifications.inApp.repositoryUpdates}
                onCheckedChange={(checked) => handleSwitchChange("inApp", "repositoryUpdates", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="inapp-model-training">Model Training Complete</Label>
                <p className="text-sm text-muted-foreground">
                  Show notifications when model training jobs are completed
                </p>
              </div>
              <Switch
                id="inapp-model-training"
                checked={notifications.inApp.modelTrainingComplete}
                onCheckedChange={(checked) => handleSwitchChange("inApp", "modelTrainingComplete", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="inapp-inference">Inference Results</Label>
                <p className="text-sm text-muted-foreground">Show notifications when inference jobs are completed</p>
              </div>
              <Switch
                id="inapp-inference"
                checked={notifications.inApp.inferenceResults}
                onCheckedChange={(checked) => handleSwitchChange("inApp", "inferenceResults", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="inapp-security">Security Alerts</Label>
                <p className="text-sm text-muted-foreground">Show notifications about security-related events</p>
              </div>
              <Switch
                id="inapp-security"
                checked={notifications.inApp.securityAlerts}
                onCheckedChange={(checked) => handleSwitchChange("inApp", "securityAlerts", checked)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSaveNotifications} disabled={isLoading}>
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Notification Settings"
          )}
        </Button>
      </div>
    </div>
  )
}
