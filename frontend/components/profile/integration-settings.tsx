"use client";

import type React from "react";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { GitBranch, GitFork, Server, Key, AlertCircle, Loader2, Check, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function IntegrationSettings() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("github");

  // GitHub integration state
  const [githubIntegration, setGithubIntegration] = useState({
    connected: false,
    token: "",
    username: "",
    testingConnection: false,
    error: null as string | null,
  });

  // GitLab integration state
  const [gitlabIntegration, setGitlabIntegration] = useState({
    connected: false,
    token: "",
    username: "",
    testingConnection: false,
    error: null as string | null,
  });

  // Self-hosted GitLab state
  const [selfHostedGitlab, setSelfHostedGitlab] = useState({
    enabled: false,
    url: "",
    token: "",
    verifySSL: true,
    testingConnection: false,
    error: null as string | null,
  });

  const handleGithubInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setGithubIntegration((prev) => ({ ...prev, [name]: value, error: null }));
  };

  const handleGitlabInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setGitlabIntegration((prev) => ({ ...prev, [name]: value, error: null }));
  };

  const handleSelfHostedGitlabInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setSelfHostedGitlab((prev) => ({ ...prev, [name]: value, error: null }));
  };

  const handleSelfHostedGitlabSwitchChange = (name: string, checked: boolean) => {
    setSelfHostedGitlab((prev) => ({ ...prev, [name]: checked, error: null }));
  };

  const testGithubConnection = async () => {
    if (!githubIntegration.token) {
      setGithubIntegration((prev) => ({ ...prev, error: "Please enter a personal access token" }));
      return;
    }

    setGithubIntegration((prev) => ({ ...prev, testingConnection: true, error: null }));

    try {
      // In a real app, this would be an API call to test the GitHub connection
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Simulate successful connection
      setGithubIntegration((prev) => ({
        ...prev,
        connected: true,
        username: "github-user",
        testingConnection: false,
      }));

      toast({
        title: "GitHub connection successful",
        description: "Your GitHub account has been connected successfully",
      });
    } catch (error) {
      setGithubIntegration((prev) => ({
        ...prev,
        testingConnection: false,
        error: "Failed to connect to GitHub. Please check your token and try again.",
      }));
    }
  };

  const testGitlabConnection = async () => {
    if (!gitlabIntegration.token) {
      setGitlabIntegration((prev) => ({ ...prev, error: "Please enter a personal access token" }));
      return;
    }

    setGitlabIntegration((prev) => ({ ...prev, testingConnection: true, error: null }));

    try {
      // In a real app, this would be an API call to test the GitLab connection
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Simulate successful connection
      setGitlabIntegration((prev) => ({
        ...prev,
        connected: true,
        username: "gitlab-user",
        testingConnection: false,
      }));

      toast({
        title: "GitLab connection successful",
        description: "Your GitLab account has been connected successfully",
      });
    } catch (error) {
      setGitlabIntegration((prev) => ({
        ...prev,
        testingConnection: false,
        error: "Failed to connect to GitLab. Please check your token and try again.",
      }));
    }
  };

  const testSelfHostedGitlabConnection = async () => {
    if (!selfHostedGitlab.url || !selfHostedGitlab.token) {
      setSelfHostedGitlab((prev) => ({ ...prev, error: "Please enter both URL and token" }));
      return;
    }

    setSelfHostedGitlab((prev) => ({ ...prev, testingConnection: true, error: null }));

    try {
      // In a real app, this would be an API call to test the self-hosted GitLab connection
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Simulate successful connection
      setSelfHostedGitlab((prev) => ({
        ...prev,
        enabled: true,
        testingConnection: false,
      }));

      toast({
        title: "Self-hosted GitLab connection successful",
        description: "Your self-hosted GitLab server has been connected successfully",
      });
    } catch (error) {
      setSelfHostedGitlab((prev) => ({
        ...prev,
        testingConnection: false,
        error: "Failed to connect to self-hosted GitLab. Please check your settings and try again.",
      }));
    }
  };

  const disconnectGithub = () => {
    setGithubIntegration({
      connected: false,
      token: "",
      username: "",
      testingConnection: false,
      error: null,
    });

    toast({
      title: "GitHub disconnected",
      description: "Your GitHub account has been disconnected",
    });
  };

  const disconnectGitlab = () => {
    setGitlabIntegration({
      connected: false,
      token: "",
      username: "",
      testingConnection: false,
      error: null,
    });

    toast({
      title: "GitLab disconnected",
      description: "Your GitLab account has been disconnected",
    });
  };

  const disconnectSelfHostedGitlab = () => {
    setSelfHostedGitlab({
      enabled: false,
      url: "",
      token: "",
      verifySSL: true,
      testingConnection: false,
      error: null,
    });

    toast({
      title: "Self-hosted GitLab disconnected",
      description: "Your self-hosted GitLab server has been disconnected",
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Git Provider Integrations</CardTitle>
          <CardDescription>
            Connect to GitHub, GitLab, or self-hosted GitLab to access your repositories
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList>
              <TabsTrigger value="github" className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                GitHub
                {githubIntegration.connected && (
                  <Badge
                    variant="outline"
                    className="ml-2 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                  >
                    <Check className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="gitlab" className="flex items-center gap-2">
                <GitFork className="h-4 w-4" />
                GitLab
                {gitlabIntegration.connected && (
                  <Badge
                    variant="outline"
                    className="ml-2 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                  >
                    <Check className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="self-hosted" className="flex items-center gap-2">
                <Server className="h-4 w-4" />
                Self-Hosted GitLab
                {selfHostedGitlab.enabled && (
                  <Badge
                    variant="outline"
                    className="ml-2 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                  >
                    <Check className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="github" className="space-y-4">
              {githubIntegration.connected ? (
                <div className="space-y-4">
                  <div className="rounded-md bg-muted p-4">
                    <div className="flex items-center gap-2">
                      <GitBranch className="h-5 w-5 text-primary" />
                      <div>
                        <h3 className="font-medium">GitHub Connected</h3>
                        <p className="text-sm text-muted-foreground">
                          Connected as{" "}
                          <span className="font-medium">{githubIntegration.username}</span>
                        </p>
                      </div>
                      <Badge className="ml-auto">Active</Badge>
                    </div>
                  </div>
                  <Button variant="outline" onClick={disconnectGithub}>
                    <X className="mr-2 h-4 w-4" />
                    Disconnect GitHub
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="github-token">Personal Access Token</Label>
                    <Input
                      id="github-token"
                      name="token"
                      type="password"
                      value={githubIntegration.token}
                      onChange={handleGithubInputChange}
                      placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    />
                    <p className="text-sm text-muted-foreground">
                      Create a personal access token with <code>repo</code> scope in your{" "}
                      <a
                        href="https://github.com/settings/tokens"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        GitHub settings
                      </a>
                      .
                    </p>
                  </div>

                  {githubIntegration.error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Error</AlertTitle>
                      <AlertDescription>{githubIntegration.error}</AlertDescription>
                    </Alert>
                  )}

                  <Button
                    onClick={testGithubConnection}
                    disabled={githubIntegration.testingConnection}
                  >
                    {githubIntegration.testingConnection ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      <>
                        <Key className="mr-2 h-4 w-4" />
                        Connect GitHub
                      </>
                    )}
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="gitlab" className="space-y-4">
              {gitlabIntegration.connected ? (
                <div className="space-y-4">
                  <div className="rounded-md bg-muted p-4">
                    <div className="flex items-center gap-2">
                      <GitFork className="h-5 w-5 text-primary" />
                      <div>
                        <h3 className="font-medium">GitLab Connected</h3>
                        <p className="text-sm text-muted-foreground">
                          Connected as{" "}
                          <span className="font-medium">{gitlabIntegration.username}</span>
                        </p>
                      </div>
                      <Badge className="ml-auto">Active</Badge>
                    </div>
                  </div>
                  <Button variant="outline" onClick={disconnectGitlab}>
                    <X className="mr-2 h-4 w-4" />
                    Disconnect GitLab
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="gitlab-token">Personal Access Token</Label>
                    <Input
                      id="gitlab-token"
                      name="token"
                      type="password"
                      value={gitlabIntegration.token}
                      onChange={handleGitlabInputChange}
                      placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
                    />
                    <p className="text-sm text-muted-foreground">
                      Create a personal access token with <code>api</code> scope in your{" "}
                      <a
                        href="https://gitlab.com/-/profile/personal_access_tokens"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        GitLab settings
                      </a>
                      .
                    </p>
                  </div>

                  {gitlabIntegration.error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Error</AlertTitle>
                      <AlertDescription>{gitlabIntegration.error}</AlertDescription>
                    </Alert>
                  )}

                  <Button
                    onClick={testGitlabConnection}
                    disabled={gitlabIntegration.testingConnection}
                  >
                    {gitlabIntegration.testingConnection ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      <>
                        <Key className="mr-2 h-4 w-4" />
                        Connect GitLab
                      </>
                    )}
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="self-hosted" className="space-y-4">
              {selfHostedGitlab.enabled ? (
                <div className="space-y-4">
                  <div className="rounded-md bg-muted p-4">
                    <div className="flex items-center gap-2">
                      <Server className="h-5 w-5 text-primary" />
                      <div>
                        <h3 className="font-medium">Self-Hosted GitLab Connected</h3>
                        <p className="text-sm text-muted-foreground">
                          Connected to <span className="font-medium">{selfHostedGitlab.url}</span>
                        </p>
                      </div>
                      <Badge className="ml-auto">Active</Badge>
                    </div>
                  </div>
                  <Button variant="outline" onClick={disconnectSelfHostedGitlab}>
                    <X className="mr-2 h-4 w-4" />
                    Disconnect Self-Hosted GitLab
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="gitlab-url">GitLab Server URL</Label>
                    <Input
                      id="gitlab-url"
                      name="url"
                      type="url"
                      value={selfHostedGitlab.url}
                      onChange={handleSelfHostedGitlabInputChange}
                      placeholder="https://gitlab.example.com"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="gitlab-self-token">Personal Access Token</Label>
                    <Input
                      id="gitlab-self-token"
                      name="token"
                      type="password"
                      value={selfHostedGitlab.token}
                      onChange={handleSelfHostedGitlabInputChange}
                      placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
                    />
                    <p className="text-sm text-muted-foreground">
                      Create a personal access token with <code>api</code> scope in your self-hosted
                      GitLab instance.
                    </p>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Switch
                      id="verify-ssl"
                      checked={selfHostedGitlab.verifySSL}
                      onCheckedChange={(checked) =>
                        handleSelfHostedGitlabSwitchChange("verifySSL", checked)
                      }
                    />
                    <Label htmlFor="verify-ssl">Verify SSL Certificate</Label>
                  </div>

                  {selfHostedGitlab.error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Error</AlertTitle>
                      <AlertDescription>{selfHostedGitlab.error}</AlertDescription>
                    </Alert>
                  )}

                  <Button
                    onClick={testSelfHostedGitlabConnection}
                    disabled={selfHostedGitlab.testingConnection}
                  >
                    {selfHostedGitlab.testingConnection ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      <>
                        <Key className="mr-2 h-4 w-4" />
                        Connect Self-Hosted GitLab
                      </>
                    )}
                  </Button>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
