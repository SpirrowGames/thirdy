"use client";

import { useState, useEffect } from "react";
import { useTasks } from "@/hooks/use-tasks";
import { useDesigns } from "@/hooks/use-designs";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TaskCard } from "./task-card";

interface TaskPanelProps {
  conversationId: string | null;
  preselectedDesignId?: string;
  onTaskDone?: (taskId: string) => void;
  autoTrigger?: boolean;
  onAutoTriggered?: () => void;
}

export function TaskPanel({ conversationId, preselectedDesignId, onTaskDone, autoTrigger, onAutoTriggered }: TaskPanelProps) {
  const {
    tasks,
    isLoading,
    isGenerating,
    error,
    generateTasks,
    updateTask,
    deleteTask,
  } = useTasks(conversationId);

  const { designs } = useDesigns(conversationId);
  const approvedDesigns = designs.filter((d) => d.status === "approved");

  const [selectedDesignId, setSelectedDesignId] = useState<string>("");

  useEffect(() => {
    if (preselectedDesignId) {
      setSelectedDesignId(preselectedDesignId);
    }
  }, [preselectedDesignId]);

  // Auto-trigger task generation when autoTrigger is set
  useEffect(() => {
    if (autoTrigger && preselectedDesignId && !isGenerating && conversationId) {
      generateTasks(preselectedDesignId);
      onAutoTriggered?.();
    }
  }, [autoTrigger, preselectedDesignId, isGenerating, conversationId, generateTasks, onAutoTriggered]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b p-3">
        <Select value={selectedDesignId} onValueChange={setSelectedDesignId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select approved design..." />
          </SelectTrigger>
          <SelectContent>
            {approvedDesigns.map((design) => (
              <SelectItem key={design.id} value={design.id}>
                {design.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          onClick={() => generateTasks(selectedDesignId)}
          disabled={!conversationId || !selectedDesignId || isGenerating}
          size="sm"
          className="w-full"
        >
          {isGenerating ? "Generating..." : "Generate Tasks"}
        </Button>
      </div>

      {error && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : tasks.length === 0 && !isGenerating ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No tasks yet. Select an approved design and click
            &quot;Generate Tasks&quot; to create implementation tasks.
          </p>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                allTasks={tasks}
                onStatusChange={(id, status) => {
                  updateTask(id, { status });
                  if (status === "done" && onTaskDone) {
                    onTaskDone(id);
                  }
                }}
                onDelete={deleteTask}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
