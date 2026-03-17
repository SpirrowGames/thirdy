"use client";

interface ErrorBannerProps {
  error: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  "Failed to fetch": "Network error. Please check your connection.",
  "502": "LLM service temporarily unavailable.",
  "peer closed connection": "Connection interrupted. Try again.",
  "timed out": "Request timed out. The model may be busy.",
};

function friendlyMessage(error: string): string {
  for (const [pattern, message] of Object.entries(FRIENDLY_MESSAGES)) {
    if (error.toLowerCase().includes(pattern.toLowerCase())) {
      return message;
    }
  }
  return error;
}

export function ErrorBanner({ error, onRetry, onDismiss }: ErrorBannerProps) {
  return (
    <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
      <div className="flex items-start justify-between gap-2">
        <span>{friendlyMessage(error)}</span>
        <div className="flex shrink-0 gap-1">
          {onRetry && (
            <button
              onClick={onRetry}
              className="rounded bg-destructive/20 px-2 py-0.5 text-xs font-medium hover:bg-destructive/30 transition-colors"
            >
              Retry
            </button>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="rounded px-1.5 py-0.5 text-xs opacity-60 hover:opacity-100 transition-opacity"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
