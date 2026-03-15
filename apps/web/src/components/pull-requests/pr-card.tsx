"use client";

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

interface PRCardProps {
  pr: PullRequestRead;
  onDelete: (prId: string) => void;
}

export function PRCard({ pr, onDelete }: PRCardProps) {
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
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(pr.id)}
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
