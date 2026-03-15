"use client";

import { useCallback, useRef, useState } from "react";
import { useVoiceTranscripts } from "@/hooks/use-voice";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VoiceTranscriptCard } from "./voice-transcript-card";

interface VoicePanelProps {
  conversationId: string | null;
}

export function VoicePanel({ conversationId }: VoicePanelProps) {
  const {
    transcripts,
    isLoading,
    isTranscribing,
    transcriptionSegments,
    classificationResult,
    transcriptionError,
    transcribeAudio,
    stopTranscription,
    deleteTranscript,
  } = useVoiceTranscripts(conversationId);

  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      transcribeAudio(file);
    },
    [transcribeAudio],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const classificationKeys = [
    "summary",
    "requirements",
    "questions",
    "decisions",
    "action_items",
  ] as const;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-3 space-y-2">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30"
          }`}
        >
          <p className="text-xs text-muted-foreground mb-2">
            Drop an audio file here, or
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={!conversationId || isTranscribing}
            onClick={() => fileInputRef.current?.click()}
          >
            {isTranscribing ? "Transcribing..." : "Choose File"}
          </Button>
        </div>
        {isTranscribing && (
          <Button
            size="sm"
            variant="ghost"
            className="w-full text-xs"
            onClick={stopTranscription}
          >
            Cancel
          </Button>
        )}
      </div>

      {transcriptionError && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {transcriptionError}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {/* Live transcription segments */}
        {isTranscribing && transcriptionSegments.length > 0 && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Transcribing...
            </p>
            <div className="text-sm space-y-1">
              {transcriptionSegments.map((seg, i) => (
                <p key={i}>
                  <span className="text-xs text-muted-foreground mr-1">
                    [{seg.start.toFixed(1)}s]
                  </span>
                  {seg.text}
                </p>
              ))}
              <span className="inline-block h-4 w-1.5 animate-pulse bg-foreground/60" />
            </div>
          </div>
        )}

        {/* Classification result from current transcription */}
        {classificationResult && !isTranscribing && (
          <div className="mb-4 rounded-lg border bg-green-500/5 p-3">
            <p className="mb-2 text-xs font-medium text-green-600">
              Classification Result
            </p>
            <div className="text-xs space-y-2">
              {classificationKeys.map((key) => {
                const value = classificationResult[key];
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
          </div>
        )}

        {/* Transcript list */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : transcripts.length === 0 && !isTranscribing ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No voice transcripts yet. Upload an audio file to get started.
          </p>
        ) : (
          <div className="space-y-3">
            {transcripts.map((t) => (
              <VoiceTranscriptCard
                key={t.id}
                transcript={t}
                onDelete={deleteTranscript}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
