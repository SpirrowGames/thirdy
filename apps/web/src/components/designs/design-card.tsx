"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DesignRead, DesignStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_COLORS: Record<DesignStatus, string> = {
  draft: "bg-yellow-500/10 text-yellow-600",
  in_review: "bg-blue-500/10 text-blue-600",
  approved: "bg-green-500/10 text-green-600",
};

const STATUS_LABELS: Record<DesignStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
};

interface DesignCardProps {
  design: DesignRead;
  onStatusChange: (designId: string, status: DesignStatus) => void;
  onDelete: (designId: string) => void;
}

export function DesignCard({
  design,
  onStatusChange,
  onDelete,
}: DesignCardProps) {
  const nextStatuses: DesignStatus[] = (
    ["draft", "in_review", "approved"] as DesignStatus[]
  ).filter((s) => s !== design.status);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {design.title}
          </CardTitle>
          <Badge variant="secondary" className={STATUS_COLORS[design.status]}>
            {STATUS_LABELS[design.status]}
          </Badge>
        </div>
        <div className="flex gap-1 pt-1">
          {nextStatuses.map((s) => (
            <Button
              key={s}
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => onStatusChange(design.id, s)}
            >
              → {STATUS_LABELS[s]}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-destructive"
            onClick={() => onDelete(design.id)}
          >
            Delete
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="prose prose-sm dark:prose-invert max-w-none max-h-96 overflow-y-auto">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {design.content}
          </ReactMarkdown>
        </div>
      </CardContent>
    </Card>
  );
}
