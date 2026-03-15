"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PullRequestRead, PRStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_COLORS: Record<PRStatus, string> = {
  creating: "bg-blue-500/10 text-blue-600",
  created: "bg-green-500/10 text-green-600",
  merged: "bg-purple-500/10 text-purple-600",
  closed: "bg-gray-500/10 text-gray-600",
  failed: "bg-red-500/10 text-red-600",
};

const STATUS_LABELS: Record<PRStatus, string> = {
  creating: "Creating",
  created: "Created",
  merged: "Merged",
  closed: "Closed",
  failed: "Failed",
};

const STATUS_TRANSITIONS: Record<PRStatus, PRStatus[]> = {
  creating: [],
  created: ["merged", "closed"],
  merged: [],
  closed: [],
  failed: [],
};

interface PRCardProps {
  pr: PullRequestRead;
  onStatusChange: (prId: string, status: PRStatus) => void;
  onDelete: (prId: string) => void;
}

export function PRCard({ pr, onStatusChange, onDelete }: PRCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const nextStatuses = STATUS_TRANSITIONS[pr.status];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {pr.pr_number ? `#${pr.pr_number} ` : ""}
            {pr.title}
          </CardTitle>
          <Badge variant="secondary" className={STATUS_COLORS[pr.status]}>
            {STATUS_LABELS[pr.status]}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground truncate">
          {pr.branch_name}
        </p>
      </CardHeader>
      <CardContent className="pt-0">
        {pr.status === "failed" && pr.error_message && (
          <div className="mb-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
            {pr.error_message}
          </div>
        )}

        {/* Status transition buttons */}
        {nextStatuses.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {nextStatuses.map((s) => (
              <Button
                key={s}
                variant="outline"
                size="sm"
                className="h-6 text-xs"
                onClick={() => onStatusChange(pr.id, s)}
              >
                Mark as {STATUS_LABELS[s]}
              </Button>
            ))}
          </div>
        )}

        <div className="flex gap-1">
          {pr.pr_url && (
            <a
              href={pr.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-6 items-center rounded-md border px-2 text-xs hover:bg-accent"
            >
              View on GitHub
            </a>
          )}
          {pr.description && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? "Hide details" : "Details"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(pr.id)}
          >
            Delete
          </Button>
        </div>

        {showDetails && pr.description && (
          <div className="prose prose-sm dark:prose-invert max-w-none mt-2 max-h-60 overflow-y-auto rounded border p-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {pr.description}
            </ReactMarkdown>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
