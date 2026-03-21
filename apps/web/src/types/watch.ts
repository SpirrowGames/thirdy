// TypeScript mirrors of shared_schemas.watch_report

export type WatchSourceType =
  | "dependency"
  | "api_change"
  | "security"
  | "competitor"
  | "ecosystem";

export type WatchImpactLevel = "none" | "low" | "medium" | "high" | "critical";

export interface WatchFinding {
  source_type: WatchSourceType;
  impact_level: WatchImpactLevel;
  title: string;
  description: string;
  source_url: string | null;
  affected_area: string | null;
  recommendation: string | null;
  is_new?: boolean;
}

export interface WatchSummary {
  total_findings: number;
  new_findings: number;
  findings_by_impact: Record<string, number>;
  findings_by_source: Record<string, number>;
  highest_impact: string;
  requires_action: boolean;
}

export interface WatchReportRead {
  id: string;
  conversation_id: string;
  job_id: string | null;
  summary: WatchSummary | null;
  findings: WatchFinding[];
  watch_targets: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface WatchTriggerRequest {
  model?: string | null;
  targets?: string[] | null;
}

export interface WatchTriggerResponse {
  job_id: string;
  conversation_id: string;
  message: string;
}
