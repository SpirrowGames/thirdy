"use client";

import { useState } from "react";
import { useAudits } from "@/hooks/use-audits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AuditReportRead, FindingSeverity } from "@/types/audit";

interface AuditPanelProps {
  conversationId: string | null;
}

const badgeColor: Record<string, string> = {
  excellent: "bg-green-500/15 text-green-700 dark:text-green-400",
  good: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  needs_improvement: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  poor: "bg-red-500/15 text-red-700 dark:text-red-400",
};

const severityColor: Record<FindingSeverity, string> = {
  info: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  warning: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  error: "bg-red-500/15 text-red-700 dark:text-red-400",
  critical: "bg-red-700/15 text-red-900 dark:text-red-300",
};

function AuditReportItem({
  report,
  onDelete,
}: {
  report: AuditReportRead;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {report.summary ? (
            <Badge
              variant="secondary"
              className={
                badgeColor[report.summary.quality_badge] ?? ""
              }
            >
              {report.summary.quality_badge.replace("_", " ")}
            </Badge>
          ) : (
            <Badge variant="secondary">{report.status}</Badge>
          )}
          {report.summary && (
            <span className="text-sm font-medium">
              {report.summary.overall_score}/100
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground">
            {new Date(report.created_at).toLocaleDateString()}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(report.id)}
          >
            ×
          </Button>
        </div>
      </div>

      {report.summary && (
        <p className="text-xs text-muted-foreground">
          {report.summary.total_findings} finding
          {report.summary.total_findings !== 1 ? "s" : ""}
        </p>
      )}

      {report.status === "pending" && (
        <p className="text-xs text-muted-foreground animate-pulse">
          Audit queued...
        </p>
      )}

      {report.status === "running" && (
        <p className="text-xs text-muted-foreground animate-pulse">
          Audit running...
        </p>
      )}

      {report.findings.length > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Hide" : "Show"} findings
        </Button>
      )}

      {expanded && (
        <div className="space-y-2 pt-1">
          {report.findings.map((f, i) => (
            <div
              key={i}
              className="rounded border bg-muted/30 p-2 space-y-1"
            >
              <div className="flex items-center gap-1.5">
                <Badge
                  variant="secondary"
                  className={`text-[10px] ${severityColor[f.severity] ?? ""}`}
                >
                  {f.severity}
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {f.category}
                </Badge>
              </div>
              <p className="text-xs font-medium">{f.title}</p>
              <p className="text-xs text-muted-foreground">{f.description}</p>
              {f.suggestion && (
                <p className="text-xs text-green-700 dark:text-green-400">
                  Suggestion: {f.suggestion}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function AuditPanel({ conversationId }: AuditPanelProps) {
  const {
    reports,
    isLoading,
    isTriggering,
    triggerError,
    triggerAudit,
    deleteAudit,
  } = useAudits(conversationId);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-3">
        <Button
          size="sm"
          className="w-full"
          onClick={triggerAudit}
          disabled={!conversationId || isTriggering}
        >
          {isTriggering ? "Queuing..." : "Run Audit"}
        </Button>
      </div>

      {triggerError && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {triggerError}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : reports.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No audit reports yet. Click &quot;Run Audit&quot; to analyze your
            project.
          </p>
        ) : (
          <div className="space-y-3">
            {reports.map((report) => (
              <AuditReportItem
                key={report.id}
                report={report}
                onDelete={deleteAudit}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
