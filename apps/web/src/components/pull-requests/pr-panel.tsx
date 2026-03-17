"use client";

import { useState, useEffect, useMemo } from "react";
import { Check, Loader2, Circle } from "lucide-react";
import { usePullRequests } from "@/hooks/use-pull-requests";
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
import { ErrorBanner } from "@/components/ui/error-banner";
import { PRCard } from "./pr-card";

interface PRPanelProps {
  conversationId: string | null;
  preselectedCodeId?: string;
  autoTrigger?: boolean;
  onAutoTriggered?: () => void;
}

const PR_STEPS = [
  { event: "pr_started", label: "Initializing" },
  { event: "branch_created", label: "Branch created" },
  { event: "files_committed", label: "Files committed" },
  { event: "pr_created", label: "PR created" },
] as const;

export function PRPanel({ conversationId, preselectedCodeId, autoTrigger, onAutoTriggered }: PRPanelProps) {
  const {
    pullRequests,
    isLoading,
    isCreating,
    progress,
    error,
    createPR,
    updatePR,
    deletePR,
  } = usePullRequests(conversationId);

  const { codes } = useCodes(conversationId);
  const { tasks } = useTasks(conversationId);
  const approvedCodes = codes.filter((c) => c.status === "approved");

  const taskTitleMap = useMemo(
    () => new Map(tasks.map((t) => [t.id, t.title])),
    [tasks],
  );

  const [selectedCodeId, setSelectedCodeId] = useState<string>("");

  useEffect(() => {
    if (preselectedCodeId) {
      setSelectedCodeId(preselectedCodeId);
    }
  }, [preselectedCodeId]);

  // Auto-trigger PR creation when autoTrigger is set
  useEffect(() => {
    if (autoTrigger && preselectedCodeId && !isCreating && conversationId) {
      createPR(preselectedCodeId);
      onAutoTriggered?.();
    }
  }, [autoTrigger, preselectedCodeId, isCreating, conversationId, createPR, onAutoTriggered]);

  // Determine which step is current based on progress
  const currentStepEvent = progress?.step
    ? (() => {
        const stepText = progress.step.toLowerCase();
        if (stepText.includes("pull request created") || stepText.includes("pr created")) return "pr_created";
        if (stepText.includes("files committed") || stepText.includes("committed")) return "files_committed";
        if (stepText.includes("branch created") || stepText.includes("branch")) return "branch_created";
        return "pr_started";
      })()
    : null;

  const currentStepIndex = currentStepEvent
    ? PR_STEPS.findIndex((s) => s.event === currentStepEvent)
    : -1;

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b p-3">
        <Select value={selectedCodeId} onValueChange={setSelectedCodeId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select approved code..." />
          </SelectTrigger>
          <SelectContent>
            {approvedCodes.map((code) => {
              const taskName = taskTitleMap.get(code.task_id);
              return (
                <SelectItem key={code.id} value={code.id}>
                  {taskName ?? `Code ${code.id.slice(0, 8)}...`}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        <Button
          onClick={() => createPR(selectedCodeId)}
          disabled={!conversationId || !selectedCodeId || isCreating}
          size="sm"
          className="w-full"
        >
          {isCreating ? "Creating PR..." : "Create Pull Request"}
        </Button>
      </div>

      {error && (
        <ErrorBanner
          error={error}
          onRetry={selectedCodeId ? () => createPR(selectedCodeId) : undefined}
        />
      )}

      <ScrollArea className="flex-1 p-3">
        {isCreating && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Creating pull request...
            </p>
            <ul className="space-y-1.5">
              {PR_STEPS.map((step, i) => {
                const isDone = i < currentStepIndex;
                const isCurrent = i === currentStepIndex;
                const isPending = i > currentStepIndex;

                let detail = "";
                if ((isDone || isCurrent) && progress?.detail) {
                  if (step.event === currentStepEvent) {
                    detail = progress.detail;
                  }
                }

                return (
                  <li key={step.event} className="flex items-center gap-2 text-xs">
                    {isDone ? (
                      <Check className="h-3.5 w-3.5 text-green-600 shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
                    ) : (
                      <Circle className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
                    )}
                    <span
                      className={
                        isPending
                          ? "text-muted-foreground/40"
                          : "text-foreground"
                      }
                    >
                      {step.label}
                      {detail && ` — ${detail}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : pullRequests.length === 0 && !isCreating ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No pull requests yet. Select approved code and click
            &quot;Create Pull Request&quot; to create a GitHub PR.
          </p>
        ) : (
          <div className="space-y-3">
            {pullRequests.map((pr) => (
              <PRCard
                key={pr.id}
                pr={pr}
                onStatusChange={(id, status) => updatePR(id, { status })}
                onDelete={deletePR}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
