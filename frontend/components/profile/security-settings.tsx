"use client";

import type React from "react";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import { AlertCircle, Loader2, Shield, KeyRound } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function SecuritySettings() {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [passwordData, setPasswordData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [sessionTimeout, setSessionTimeout] = useState(60);

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPasswordData((prev) => ({ ...prev, [name]: value }));
    setPasswordError(null);
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    // Validate passwords
    if (!passwordData.currentPassword) {
      setPasswordError("Current password is required");
      return;
    }

    if (!passwordData.newPassword) {
      setPasswordError("New password is required");
      return;
    }

    if (passwordData.newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters long");
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setPasswordError("New passwords do not match");
      return;
    }

    setIsLoading(true);

    try {
      // In a real app, this would be an API call
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Reset form
      setPasswordData({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });

      toast({
        title: "Password updated",
        description: "Your password has been updated successfully",
      });
    } catch (error) {
      setPasswordError("Failed to update password. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleTwoFactor = async (checked: boolean) => {
    // In a real app, this would be an API call
    setTwoFactorEnabled(checked);

    toast({
      title: checked ? "Two-factor authentication enabled" : "Two-factor authentication disabled",
      description: checked
        ? "Your account is now more secure"
        : "Two-factor authentication has been disabled",
    });
  };

  const handleSessionTimeoutChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number.parseInt(e.target.value);
    if (!isNaN(value) && value >= 5) {
      setSessionTimeout(value);
    }
  };

  const handleSaveSessionTimeout = () => {
    // In a real app, this would be an API call
    toast({
      title: "Session timeout updated",
      description: `Session timeout set to ${sessionTimeout} minutes`,
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>Update your password to keep your account secure</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current Password</Label>
              <Input
                id="currentPassword"
                name="currentPassword"
                type="password"
                value={passwordData.currentPassword}
                onChange={handlePasswordChange}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="newPassword">New Password</Label>
              <Input
                id="newPassword"
                name="newPassword"
                type="password"
                value={passwordData.newPassword}
                onChange={handlePasswordChange}
              />
              <p className="text-sm text-muted-foreground">
                Password must be at least 8 characters long and include a mix of letters, numbers,
                and symbols.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <Input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                value={passwordData.confirmPassword}
                onChange={handlePasswordChange}
              />
            </div>

            {passwordError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{passwordError}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                <>
                  <KeyRound className="mr-2 h-4 w-4" />
                  Change Password
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Two-Factor Authentication</CardTitle>
          <CardDescription>Add an extra layer of security to your account</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="two-factor">Two-Factor Authentication</Label>
              <p className="text-sm text-muted-foreground">
                Require a verification code when signing in
              </p>
            </div>
            <Switch
              id="two-factor"
              checked={twoFactorEnabled}
              onCheckedChange={handleToggleTwoFactor}
            />
          </div>

          {twoFactorEnabled && (
            <Alert>
              <Shield className="h-4 w-4" />
              <AlertTitle>Two-factor authentication is enabled</AlertTitle>
              <AlertDescription>
                Your account is protected with an additional layer of security.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session Settings</CardTitle>
          <CardDescription>Manage your session timeout and security preferences</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="session-timeout">Session Timeout (minutes)</Label>
            <div className="flex items-center gap-2">
              <Input
                id="session-timeout"
                type="number"
                min="5"
                value={sessionTimeout}
                onChange={handleSessionTimeoutChange}
                className="w-24"
              />
              <Button onClick={handleSaveSessionTimeout}>Save</Button>
            </div>
            <p className="text-sm text-muted-foreground">
              You will be automatically logged out after this period of inactivity
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
