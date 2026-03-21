// TypeScript mirrors of shared_schemas.spec_review

export type ReviewIssueSeverity = "critical" | "warning" | "info";
export type ReviewIssueCategory =
  | "contradiction"
  | "gap"
  | "ambiguity"
  | "inconsistency";

export interface SpecReviewIssue {
  severity: ReviewIssueSeverity;
  category: ReviewIssueCategory;
  title: string;
  description: string;
  location: string | null;
}

export interface SpecReviewSuggestion {
  severity: ReviewIssueSeverity;
  title: string;
  description: string;
  before: string | null;
  after: string | null;
  section: string | null;
  status: "pending" | "applied" | "dismissed";
  related_issue_index: number | null;
}

export interface SpecReviewQuestion {
  question: string;
  context: string | null;
  priority: "high" | "medium" | "low";
}

export interface SpecReviewSummary {
  quality_score: number;
  quality_badge: string;
  total_issues: number;
  total_suggestions: number;
  total_questions: number;
  issues_by_category: Record<string, number>;
  issues_by_severity: Record<string, number>;
}

export interface SpecReviewRead {
  id: string;
  specification_id: string;
  conversation_id: string;
  job_id: string | null;
  status: string;
  scope: string;
  summary: SpecReviewSummary | null;
  issues: SpecReviewIssue[];
  suggestions: SpecReviewSuggestion[];
  questions: SpecReviewQuestion[];
  created_at: string;
  updated_at: string;
}

export interface SpecReviewTriggerResponse {
  job_id: string;
  specification_id: string;
  conversation_id: string;
  message: string;
}

export interface SuggestionApplyResponse {
  preview_diff: string | null;
  applied: boolean;
  updated_content: string | null;
}
