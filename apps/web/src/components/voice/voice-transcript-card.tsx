"use client";

import { useState } from "react";
import type { VoiceTranscriptRead, VoiceTranscriptStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_COLORS: Record<VoiceTranscriptStatus, string> = {
  processing: "bg-blue-500/10 text-blue-600",
  completed: "bg-green-500/10 text-green-600",
  failed: "bg-red-500/10 text-red-600",
};

const STATUS_LABELS: Record<VoiceTranscriptStatus, string> = {
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const CLASSIFICATION_KEYS = [
  "summary",
  "requirements",
  "questions",
  "decisions",
  "action_items",
] as const;

interface VoiceTranscriptCardProps {
  transcript: VoiceTranscriptRead;
  onDelete: (id: string) => void;
}

export function VoiceTranscriptCard({
  transcript,
  onDelete,
}: VoiceTranscriptCardProps) {
  const [showText, setShowText] = useState(false);
  const [showClassification, setShowClassification] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {transcript.filename}
          </CardTitle>
          <Badge
            variant="secondary"
            className={STATUS_COLORS[transcript.status]}
          >
            {STATUS_LABELS[transcript.status]}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {transcript.language ?? "auto"} · {formatDuration(transcript.duration_seconds)}
        </p>
      </CardHeader>
      <CardContent className="pt-0">
        {transcript.status === "failed" && transcript.error_message && (
          <div className="mb-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
            {transcript.error_message}
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          {transcript.transcript && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setShowText(!showText)}
            >
              {showText ? "Hide text" : "Transcript"}
            </Button>
          )}
          {transcript.classification && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setShowClassification(!showClassification)}
            >
              {showClassification ? "Hide classification" : "Classification"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(transcript.id)}
          >
            Delete
          </Button>
        </div>

        {showText && transcript.transcript && (
          <div className="mt-2 max-h-60 overflow-y-auto rounded border p-2 text-xs whitespace-pre-wrap">
            {transcript.transcript}
          </div>
        )}

        {showClassification && transcript.classification && (
          <div className="mt-2 max-h-60 overflow-y-auto rounded border p-2 text-xs space-y-2">
            {CLASSIFICATION_KEYS.map((key) => {
              const value = transcript.classification?.[key];
              if (!value) return null;
              return (
                <div key={key}>
                  <p className="font-medium capitalize">
                    {key.replace("_", " ")}
                  </p>
                  {typeof value === "string" ? (
                    <p className="text-muted-foreground">{value}</p>
                  ) : Array.isArray(value) ? (
                    <ul className="list-disc pl-4 text-muted-foreground">
                      {(value as string[]).map((item, i) => (
                        <li key={i}>{String(item)}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground">
                      {JSON.stringify(value)}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
