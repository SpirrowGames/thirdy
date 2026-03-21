"use client";

import { useState } from "react";
import { useSpecs } from "@/hooks/use-specs";
import { useSpecReviews } from "@/hooks/use-spec-reviews";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type {
  SpecReviewRead,
  SpecReviewSuggestion,
  ReviewIssueSeverity,
  ReviewIssueCategory,
} from "@/types/spec-review";

interface SpecReviewStandalonePanelProps {
  conversationId: string | null;
  onSendToChat?: (text: string) => void;
}

const badgeColor: Record<string, string> = {
  excellent: "bg-green-500/15 text-green-700 dark:text-green-400",
  good: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  needs_improvement: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  poor: "bg-red-500/15 text-red-700 dark:text-red-400",
};

const severityColor: Record<ReviewIssueSeverity, string> = {
  critical: "bg-red-700/15 text-red-900 dark:text-red-300",
  warning: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  info: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
};

const categoryLabel: Record<ReviewIssueCategory, string> = {
  contradiction: "Contradiction",
  gap: "Gap",
  ambiguity: "Ambiguity",
  inconsistency: "Inconsistency",
};

const priorityColor: Record<string, string> = {
  high: "bg-red-500/15 text-red-700 dark:text-red-400",
  medium: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  low: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
};

const suggestionStatusColor: Record<string, string> = {
  pending: "",
  applied: "opacity-50 border-green-500/30",
  dismissed: "opacity-40 line-through",
};

type Tab = "issues" | "suggestions" | "questions";

function ReviewDetail({
  review,
  onApply,
  onDismiss,
  onSendToChat,
  onDelete,
}: {
  review: SpecReviewRead;
  onApply: (reviewId: string, idx: number) => void;
  onDismiss: (reviewId: string, idx: number) => void;
  onSendToChat?: (text: string) => void;
  onDelete: (reviewId: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("issues");
  const [expanded, setExpanded] = useState(true);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "issues", label: "Issues", count: review.issues.length },
    { key: "suggestions", label: "Suggestions", count: review.suggestions.length },
    { key: "questions", label: "Questions", count: review.questions.length },
  ];

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {review.summary ? (
            <>
              <Badge
                variant="secondary"
                className={badgeColor[review.summary.quality_badge] ?? ""}
              >
                {review.summary.quality_badge.replace("_", " ")}
              </Badge>
              <span className="text-sm font-medium">
                {review.summary.quality_score}/100
              </span>
            </>
          ) : (
            <Badge variant="secondary">{review.status}</Badge>
          )}
          <Badge variant="outline" className="text-[10px]">
            {review.scope}
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground">
            {new Date(review.created_at).toLocaleDateString()}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(review.id)}
          >
            ×
          </Button>
        </div>
      </div>

      {review.status === "pending" && (
        <p className="text-xs text-muted-foreground animate-pulse">
          Review queued...
        </p>
      )}
      {review.status === "running" && (
        <p className="text-xs text-muted-foreground animate-pulse">
          Reviewing specification...
        </p>
      )}

      {review.status === "completed" && (
        <>
          {review.summary && (
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>{review.summary.total_issues} issues</span>
              <span>{review.summary.total_suggestions} suggestions</span>
              <span>{review.summary.total_questions} questions</span>
            </div>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Collapse" : "Expand"}
          </Button>

          {expanded && (
            <>
              <div className="flex gap-1 border-b pb-1">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`px-2 py-1 text-xs rounded-t transition-colors ${
                      activeTab === tab.key
                        ? "bg-muted font-medium"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>

              {activeTab === "issues" && (
                <div className="space-y-2 pt-1">
                  {review.issues.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">No issues found.</p>
                  ) : (
                    review.issues.map((issue, i) => (
                      <div key={i} className="rounded border bg-muted/30 p-2 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <Badge variant="secondary" className={`text-[10px] ${severityColor[issue.severity]}`}>
                            {issue.severity}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {categoryLabel[issue.category] ?? issue.category}
                          </Badge>
                          {issue.location && (
                            <span className="text-[10px] text-muted-foreground">{issue.location}</span>
                          )}
                        </div>
                        <p className="text-xs font-medium">{issue.title}</p>
                        <p className="text-xs text-muted-foreground">{issue.description}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {activeTab === "suggestions" && (
                <div className="space-y-2 pt-1">
                  {review.suggestions.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">No suggestions.</p>
                  ) : (
                    review.suggestions.map((suggestion, i) => (
                      <SuggestionItem
                        key={i}
                        suggestion={suggestion}
                        index={i}
                        reviewId={review.id}
                        onApply={onApply}
                        onDismiss={onDismiss}
                      />
                    ))
                  )}
                </div>
              )}

              {activeTab === "questions" && (
                <div className="space-y-2 pt-1">
                  {review.questions.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">No questions.</p>
                  ) : (
                    review.questions.map((q, i) => (
                      <div key={i} className="rounded border bg-muted/30 p-2 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <Badge variant="secondary" className={`text-[10px] ${priorityColor[q.priority]}`}>
                            {q.priority}
                          </Badge>
                        </div>
                        <p className="text-xs font-medium">{q.question}</p>
                        {q.context && <p className="text-xs text-muted-foreground">{q.context}</p>}
                        {onSendToChat && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs text-blue-600"
                            onClick={() => onSendToChat(q.question)}
                          >
                            Send to Chat
                          </Button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function SuggestionItem({
  suggestion,
  index,
  reviewId,
  onApply,
  onDismiss,
}: {
  suggestion: SpecReviewSuggestion;
  index: number;
  reviewId: string;
  onApply: (reviewId: string, idx: number) => void;
  onDismiss: (reviewId: string, idx: number) => void;
}) {
  return (
    <div className={`rounded border bg-muted/30 p-2 space-y-1 ${suggestionStatusColor[suggestion.status] ?? ""}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Badge variant="secondary" className={`text-[10px] ${severityColor[suggestion.severity]}`}>
            {suggestion.severity}
          </Badge>
          {suggestion.status !== "pending" && (
            <Badge
              variant="outline"
              className={`text-[10px] ${suggestion.status === "applied" ? "text-green-600" : "text-muted-foreground"}`}
            >
              {suggestion.status}
            </Badge>
          )}
        </div>
        {suggestion.status === "pending" && (
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-green-600" onClick={() => onApply(reviewId, index)}>
              Apply
            </Button>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground" onClick={() => onDismiss(reviewId, index)}>
              Dismiss
            </Button>
          </div>
        )}
      </div>
      <p className="text-xs font-medium">{suggestion.title}</p>
      <p className="text-xs text-muted-foreground">{suggestion.description}</p>
      {suggestion.before && (
        <div className="rounded bg-red-500/5 p-1.5 text-[11px] font-mono text-red-700 dark:text-red-400">
          - {suggestion.before}
        </div>
      )}
      {suggestion.after && (
        <div className="rounded bg-green-500/5 p-1.5 text-[11px] font-mono text-green-700 dark:text-green-400">
          + {suggestion.after}
        </div>
      )}
    </div>
  );
}

export function SpecReviewStandalonePanel({
  conversationId,
  onSendToChat,
}: SpecReviewStandalonePanelProps) {
  const { specs } = useSpecs(conversationId);
  const [selectedSpecId, setSelectedSpecId] = useState<string | null>(null);

  // Auto-select first spec if none selected
  const effectiveSpecId = selectedSpecId ?? specs[0]?.id ?? null;

  const {
    reviews,
    isLoading,
    isTriggering,
    triggerError,
    triggerReview,
    applySuggestion,
    dismissSuggestion,
    deleteReview,
  } = useSpecReviews(conversationId, effectiveSpecId);

  const handleApply = async (reviewId: string, idx: number) => {
    await applySuggestion(reviewId, idx, true);
  };

  const selectedSpec = specs.find((s) => s.id === effectiveSpecId);

  return (
    <div className="flex h-full flex-col">
      {/* Header: spec selector + review trigger */}
      <div className="border-b p-3 space-y-2">
        {specs.length > 1 && (
          <select
            value={effectiveSpecId ?? ""}
            onChange={(e) => setSelectedSpecId(e.target.value || null)}
            className="w-full rounded border bg-background px-2 py-1 text-xs"
          >
            {specs.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} ({s.status})
              </option>
            ))}
          </select>
        )}
        {selectedSpec && (
          <div className="text-xs text-muted-foreground truncate">
            {selectedSpec.title}
          </div>
        )}
        <div className="flex gap-2">
          <Button
            size="sm"
            className="flex-1"
            onClick={() => triggerReview("full")}
            disabled={!conversationId || !effectiveSpecId || isTriggering}
          >
            {isTriggering ? "Queuing..." : "Review Spec"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => triggerReview("quick")}
            disabled={!conversationId || !effectiveSpecId || isTriggering}
          >
            Quick
          </Button>
        </div>
      </div>

      {triggerError && (
        <div className="border-b bg-destructive/10 p-3 text-xs text-destructive">
          {triggerError}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {!effectiveSpecId ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No specifications yet. Extract a spec first, then review it here.
          </p>
        ) : isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 1 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : reviews.length === 0 ? (
          <div className="py-8 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              No reviews yet.
            </p>
            <p className="text-xs text-muted-foreground">
              Click &quot;Review Spec&quot; to let AI analyze your specification
              for contradictions, gaps, and improvements.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {reviews.map((review) => (
              <ReviewDetail
                key={review.id}
                review={review}
                onApply={handleApply}
                onDismiss={dismissSuggestion}
                onSendToChat={onSendToChat}
                onDelete={deleteReview}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
