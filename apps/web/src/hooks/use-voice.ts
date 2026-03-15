"use client";

import { useCallback, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";
import { streamSSEUpload, type SSEHandlers } from "@/lib/sse";
import type { VoiceTranscriptRead, TranscriptSegment } from "@/types/api";

export function useVoiceTranscripts(conversationId: string | null) {
  const {
    data: transcripts,
    error,
    mutate,
  } = useSWR<VoiceTranscriptRead[]>(
    conversationId
      ? `/conversations/${conversationId}/voice/transcripts`
      : null,
  );

  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionSegments, setTranscriptionSegments] = useState<
    TranscriptSegment[]
  >([]);
  const [classificationResult, setClassificationResult] = useState<
    Record<string, unknown> | null
  >(null);
  const [transcriptionError, setTranscriptionError] = useState<string | null>(
    null,
  );
  const controllerRef = useRef<AbortController | null>(null);

  const transcribeAudio = useCallback(
    (file: File, language?: string) => {
      if (!conversationId) return;

      setIsTranscribing(true);
      setTranscriptionSegments([]);
      setClassificationResult(null);
      setTranscriptionError(null);

      const formData = new FormData();
      formData.append("file", file);
      if (language) {
        formData.append("language", language);
      }
      formData.append("add_to_conversation", "true");

      const handlers: SSEHandlers = {
        onEvent(event, data) {
          const d = data as Record<string, unknown>;
          switch (event) {
            case "segment":
              setTranscriptionSegments((prev) => [
                ...prev,
                {
                  start: d.start as number,
                  end: d.end as number,
                  text: d.text as string,
                },
              ]);
              break;
            case "classification_complete":
              setClassificationResult(
                (d.classification as Record<string, unknown>) ?? null,
              );
              break;
            case "error":
              setTranscriptionError((d.detail as string) ?? "Unknown error");
              break;
            case "done":
              setIsTranscribing(false);
              mutate();
              break;
          }
        },
        onError(err) {
          setTranscriptionError(err.message);
          setIsTranscribing(false);
        },
        onDone() {
          setIsTranscribing(false);
        },
      };

      controllerRef.current = streamSSEUpload(
        `/conversations/${conversationId}/voice/transcribe`,
        formData,
        handlers,
      );
    },
    [conversationId, mutate],
  );

  const stopTranscription = useCallback(() => {
    controllerRef.current?.abort();
    setIsTranscribing(false);
  }, []);

  const deleteTranscript = useCallback(
    async (id: string) => {
      await api.del(`/voice/transcripts/${id}`);
      await mutate();
    },
    [mutate],
  );

  return {
    transcripts: transcripts ?? [],
    isLoading: !transcripts && !error,
    error,
    isTranscribing,
    transcriptionSegments,
    classificationResult,
    transcriptionError,
    transcribeAudio,
    stopTranscription,
    deleteTranscript,
  };
}
