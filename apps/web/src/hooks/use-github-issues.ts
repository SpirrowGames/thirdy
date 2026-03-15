"use client";

import { useCallback, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";
import { streamSSE, type SSEHandlers } from "@/lib/sse";
import type { GitHubIssueRead, GitHubIssueUpdate } from "@/types/api";

export function useGitHubIssues(conversationId: string | null) {
  const {
    data: issues,
    error,
    mutate,
  } = useSWR<GitHubIssueRead[]>(
    conversationId ? `/conversations/${conversationId}/issues` : null,
  );

  const [isStructuring, setIsStructuring] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [structuredPreview, setStructuredPreview] = useState<{
    issue_id: string;
    title: string;
    body: string;
    labels: string[];
  } | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [issueError, setIssueError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // Step 1: Structure natural language text into a draft issue via LLM
  const structureIssue = useCallback(
    (text: string) => {
      if (!conversationId) return;

      setIsStructuring(true);
      setStreamingContent("");
      setStructuredPreview(null);
      setIssueError(null);

      const handlers: SSEHandlers = {
        onEvent(event, data) {
          const d = data as Record<string, unknown>;
          switch (event) {
            case "token":
              setStreamingContent((prev) => prev + (d.content as string));
              break;
            case "structured":
              setStructuredPreview({
                issue_id: d.issue_id as string,
                title: d.title as string,
                body: d.body as string,
                labels: d.labels as string[],
              });
              break;
            case "error":
              setIssueError((d.detail as string) ?? "Unknown error");
              break;
            case "done":
              setIsStructuring(false);
              mutate();
              break;
          }
        },
        onError(err) {
          setIssueError(err.message);
          setIsStructuring(false);
        },
        onDone() {
          setIsStructuring(false);
        },
      };

      controllerRef.current = streamSSE(
        `/conversations/${conversationId}/issues/structure`,
        { text },
        handlers,
      );
    },
    [conversationId, mutate],
  );

  // Step 2: Publish a draft issue to GitHub
  const createIssue = useCallback(
    (issueId: string) => {
      if (!conversationId) return;

      setIsCreating(true);
      setIssueError(null);

      const handlers: SSEHandlers = {
        onEvent(event, data) {
          const d = data as Record<string, unknown>;
          switch (event) {
            case "issue_created":
              // Issue created on GitHub
              break;
            case "error":
              setIssueError((d.detail as string) ?? "Unknown error");
              break;
            case "done":
              setIsCreating(false);
              setStructuredPreview(null);
              mutate();
              break;
          }
        },
        onError(err) {
          setIssueError(err.message);
          setIsCreating(false);
        },
        onDone() {
          setIsCreating(false);
        },
      };

      controllerRef.current = streamSSE(
        `/conversations/${conversationId}/issues/create`,
        { issue_id: issueId },
        handlers,
      );
    },
    [conversationId, mutate],
  );

  const updateIssue = useCallback(
    async (issueId: string, update: GitHubIssueUpdate) => {
      const updated = await api.patch<GitHubIssueRead>(
        `/issues/${issueId}`,
        update,
      );
      await mutate();
      return updated;
    },
    [mutate],
  );

  const deleteIssue = useCallback(
    async (issueId: string) => {
      await api.del(`/issues/${issueId}`);
      await mutate();
    },
    [mutate],
  );

  const stopStream = useCallback(() => {
    controllerRef.current?.abort();
    setIsStructuring(false);
    setIsCreating(false);
  }, []);

  return {
    issues: issues ?? [],
    isLoading: !issues && !error,
    error,
    isStructuring,
    isCreating,
    structuredPreview,
    streamingContent,
    issueError,
    structureIssue,
    createIssue,
    updateIssue,
    deleteIssue,
    stopStream,
  };
}
