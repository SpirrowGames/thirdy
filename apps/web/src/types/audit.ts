// TypeScript mirrors of shared_schemas.audit_report

export type FindingSeverity = "info" | "warning" | "error" | "critical";
export type FindingCategory =
  | "consistency"
  | "completeness"
  | "quality"
  | "dependency"
  | "redundancy";

export interface AuditFinding {
  severity: FindingSeverity;
  category: FindingCategory;
  title: string;
  description: string;
  affected_entity_type: string | null;
  affected_entity_id: string | null;
  suggestion: string | null;
}

export interface AuditSummary {
  overall_score: number;
  quality_badge: string;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  analyzed_entities: Record<string, number>;
}

export interface AuditReportRead {
  id: string;
  conversation_id: string;
  job_id: string | null;
  summary: AuditSummary | null;
  findings: AuditFinding[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AuditTriggerRequest {
  model?: string | null;
  scope?: string;
}

export interface AuditTriggerResponse {
  job_id: string;
  conversation_id: string;
  message: string;
}
