"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { GitHubIssueRead, IssueStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_COLORS: Record<IssueStatus, string> = {
  draft: "bg-yellow-500/10 text-yellow-600",
  creating: "bg-blue-500/10 text-blue-600",
  created: "bg-green-500/10 text-green-600",
  closed: "bg-gray-500/10 text-gray-600",
  failed: "bg-red-500/10 text-red-600",
};

const STATUS_LABELS: Record<IssueStatus, string> = {
  draft: "Draft",
  creating: "Creating",
  created: "Created",
  closed: "Closed",
  failed: "Failed",
};

interface IssueCardProps {
  issue: GitHubIssueRead;
  onDelete: (id: string) => void;
}

export function IssueCard({ issue, onDelete }: IssueCardProps) {
  const [showBody, setShowBody] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {issue.issue_number ? `#${issue.issue_number} ` : ""}
            {issue.title}
          </CardTitle>
          <Badge variant="secondary" className={STATUS_COLORS[issue.status]}>
            {STATUS_LABELS[issue.status]}
          </Badge>
        </div>
        {issue.labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {issue.labels.map((label) => (
              <Badge key={label} variant="outline" className="text-[10px] px-1.5 py-0">
                {label}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="pt-0">
        {issue.status === "failed" && issue.error_message && (
          <div className="mb-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
            {issue.error_message}
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          {issue.issue_url && (
            <a
              href={issue.issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-6 items-center rounded-md border px-2 text-xs hover:bg-accent"
            >
              View on GitHub
            </a>
          )}
          {issue.body && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setShowBody(!showBody)}
            >
              {showBody ? "Hide body" : "Details"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(issue.id)}
          >
            Delete
          </Button>
        </div>

        {showBody && issue.body && (
          <div className="prose prose-sm dark:prose-invert max-w-none mt-2 max-h-60 overflow-y-auto rounded border p-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {issue.body}
            </ReactMarkdown>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
