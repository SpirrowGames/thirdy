"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { GeneratedCodeRead, CodeStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_COLORS: Record<CodeStatus, string> = {
  draft: "bg-yellow-500/10 text-yellow-600",
  approved: "bg-green-500/10 text-green-600",
  rejected: "bg-red-500/10 text-red-600",
};

const STATUS_LABELS: Record<CodeStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
};

const STATUS_TRANSITIONS: Record<CodeStatus, CodeStatus[]> = {
  draft: ["approved", "rejected"],
  approved: ["rejected"],
  rejected: ["draft"],
};

interface CodeCardProps {
  code: GeneratedCodeRead;
  taskTitle?: string;
  onStatusChange: (codeId: string, status: CodeStatus) => void;
  onDelete: (codeId: string) => void;
}

export function CodeCard({
  code,
  taskTitle,
  onStatusChange,
  onDelete,
}: CodeCardProps) {
  const [expanded, setExpanded] = useState(false);
  const nextStatuses = STATUS_TRANSITIONS[code.status];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {taskTitle ?? "Generated Code"}
          </CardTitle>
          <Badge variant="secondary" className={STATUS_COLORS[code.status]}>
            {STATUS_LABELS[code.status]}
          </Badge>
        </div>
        <div className="flex flex-wrap gap-1 pt-1">
          {nextStatuses.map((s) => (
            <Button
              key={s}
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => onStatusChange(code.id, s)}
            >
              → {STATUS_LABELS[s]}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(code.id)}
          >
            Delete
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {expanded ? "Hide code" : "Show code"}
        </button>
        {expanded && (
          <div className="prose prose-sm dark:prose-invert max-w-none mt-2 max-h-96 overflow-y-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {code.content}
            </ReactMarkdown>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
