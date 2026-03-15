"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type { GeneratedTaskRead, GeneratedTaskUpdate } from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export function useTasks(conversationId: string | null) {
  const {
    data: tasks,
    mutate,
    isLoading,
  } = useSWR<GeneratedTaskRead[]>(
    conversationId
      ? `/conversations/${conversationId}/tasks`
      : null,
  );

  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateTasks = useCallback(
    (designId: string) => {
      if (!conversationId || isGenerating) return;

      setIsGenerating(true);
      setError(null);

      streamSSE(
        `/conversations/${conversationId}/tasks/generate`,
        { design_id: designId },
        {
          onEvent: (event, data) => {
            switch (event) {
              case "task_found": {
                const task = data as GeneratedTaskRead;
                mutate((prev) => [...(prev ?? []), task], { revalidate: false });
                break;
              }
              case "done": {
                setIsGenerating(false);
                mutate();
                break;
              }
              case "error": {
                setError((data as { detail: string }).detail);
                setIsGenerating(false);
                break;
              }
            }
          },
          onError: (err) => {
            setError(err.message);
            setIsGenerating(false);
          },
        },
      );
    },
    [conversationId, isGenerating, mutate],
  );

  const updateTask = async (taskId: string, update: GeneratedTaskUpdate) => {
    const updated = await api.patch<GeneratedTaskRead>(
      `/tasks/${taskId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deleteTask = async (taskId: string) => {
    await api.del(`/tasks/${taskId}`);
    await mutate();
  };

  return {
    tasks: tasks ?? [],
    isLoading,
    isGenerating,
    error,
    generateTasks,
    updateTask,
    deleteTask,
  };
}
