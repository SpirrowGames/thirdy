"use client";

import { useState } from "react";
import type { GeneratedTaskRead, TaskPriority, TaskStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const PRIORITY_COLORS: Record<TaskPriority, string> = {
  low: "bg-gray-500/10 text-gray-600",
  medium: "bg-blue-500/10 text-blue-600",
  high: "bg-orange-500/10 text-orange-600",
  critical: "bg-red-500/10 text-red-600",
};

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

const STATUS_COLORS: Record<TaskStatus, string> = {
  pending: "bg-yellow-500/10 text-yellow-600",
  in_progress: "bg-blue-500/10 text-blue-600",
  done: "bg-green-500/10 text-green-600",
  skipped: "bg-gray-500/10 text-gray-600",
};

const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  done: "Done",
  skipped: "Skipped",
};

const STATUS_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  pending: ["in_progress", "skipped"],
  in_progress: ["done", "skipped"],
  done: [],
  skipped: ["pending"],
};

interface TaskCardProps {
  task: GeneratedTaskRead;
  allTasks: GeneratedTaskRead[];
  onStatusChange: (taskId: string, status: TaskStatus) => void;
  onDelete: (taskId: string) => void;
}

export function TaskCard({
  task,
  allTasks,
  onStatusChange,
  onDelete,
}: TaskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const nextStatuses = STATUS_TRANSITIONS[task.status];

  const dependencyTitles = task.dependencies
    .map((depId) => allTasks.find((t) => t.id === depId)?.title)
    .filter(Boolean);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {task.title}
          </CardTitle>
          <div className="flex shrink-0 gap-1">
            <Badge variant="secondary" className={PRIORITY_COLORS[task.priority]}>
              {PRIORITY_LABELS[task.priority]}
            </Badge>
            <Badge variant="secondary" className={STATUS_COLORS[task.status]}>
              {STATUS_LABELS[task.status]}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 pt-1">
          {nextStatuses.map((s) => (
            <Button
              key={s}
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => onStatusChange(task.id, s)}
            >
              → {STATUS_LABELS[s]}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(task.id)}
          >
            Delete
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {dependencyTitles.length > 0 && (
          <div className="mb-2">
            <p className="text-xs font-medium text-muted-foreground">
              Depends on:
            </p>
            <ul className="ml-4 list-disc text-xs text-muted-foreground">
              {dependencyTitles.map((title, i) => (
                <li key={i}>{title}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {expanded ? "Hide details" : "Show details"}
        </button>
        {expanded && (
          <p className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">
            {task.description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
