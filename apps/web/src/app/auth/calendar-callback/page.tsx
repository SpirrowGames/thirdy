"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function CalendarCallbackHandler() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState("Processing...");

  const status = searchParams.get("status");
  const error = searchParams.get("message");

  useEffect(() => {
    if (status === "success") {
      setMessage("Google Calendar connected successfully! Returning...");
    } else if (status === "error") {
      setMessage(`Failed to connect: ${error || "Unknown error"}`);
    }

    // Auto-close or navigate back after a short delay
    const timer = setTimeout(() => {
      if (window.opener) {
        window.close();
      } else {
        window.history.back();
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [status, error]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center space-y-4">
        {status === "success" ? (
          <div className="text-green-600 text-lg font-medium">{message}</div>
        ) : status === "error" ? (
          <div className="text-red-600 text-lg font-medium">{message}</div>
        ) : (
          <p className="text-muted-foreground">{message}</p>
        )}
      </div>
    </div>
  );
}

export default function CalendarCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <CalendarCallbackHandler />
    </Suspense>
  );
}
