"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = `${API_URL}/auth/google`;
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Thirdy</CardTitle>
          <p className="text-sm text-muted-foreground">
            Sign in to continue
          </p>
        </CardHeader>
        <CardContent>
          <Button
            onClick={handleGoogleLogin}
            className="w-full"
            size="lg"
          >
            Sign in with Google
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
