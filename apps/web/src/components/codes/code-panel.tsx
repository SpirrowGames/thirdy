"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCodes } from "@/hooks/use-codes";
import { useTasks } from "@/hooks/use-tasks";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CodeCard } from "./code-card";

interface CodePanelProps {
  conversationId: string | null;
  preselectedTaskId?: string;
  onCodeApproved?: (codeId: string) => void;
}

export function CodePanel({ conversationId, preselectedTaskId, onCodeApproved }: CodePanelProps) {
  const {
    codes,
    isLoading,
    isGenerating,
    generatingContent,
    error,
    generateCode,
    updateCode,
    deleteCode,
  } = useCodes(conversationId);

  const { tasks } = useTasks(conversationId);
  const doneTasks = tasks.filter((t) => t.status === "done");

  const [selectedTaskId, setSelectedTaskId] = useState<string>("");

  useEffect(() => {
    if (preselectedTaskId) {
      setSelectedTaskId(preselectedTaskId);
    }
  }, [preselectedTaskId]);

  const taskTitleMap = new Map(tasks.map((t) => [t.id, t.title]));

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b p-3">
        <Select value={selectedTaskId} onValueChange={setSelectedTaskId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select a done task..." />
          </SelectTrigger>
          <SelectContent>
            {doneTasks.map((task) => (
              <SelectItem key={task.id} value={task.id}>
                {task.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          onClick={() => generateCode(selectedTaskId)}
          disabled={!conversationId || !selectedTaskId || isGenerating}
          size="sm"
          className="w-full"
        >
          {isGenerating ? "Generating..." : "Generate Code"}
        </Button>
      </div>

      {error && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isGenerating && generatingContent && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Generating code...
            </p>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {generatingContent}
              </ReactMarkdown>
              <span className="inline-block h-4 w-1.5 animate-pulse bg-foreground/60" />
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : codes.length === 0 && !isGenerating ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No generated code yet. Select a done task and click
            &quot;Generate Code&quot; to create implementation code.
          </p>
        ) : (
          <div className="space-y-3">
            {codes.map((code) => (
              <CodeCard
                key={code.id}
                code={code}
                taskTitle={taskTitleMap.get(code.task_id)}
                onStatusChange={(id, newStatus) => {
                  updateCode(id, { status: newStatus });
                  if (newStatus === "approved" && onCodeApproved) {
                    onCodeApproved(id);
                  }
                }}
                onDelete={deleteCode}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
