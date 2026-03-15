// TypeScript mirrors of Pydantic schemas (packages/shared-schemas)

// --- Auth ---
export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// --- User ---
export interface UserRead {
  id: string;
  email: string;
  name: string;
  picture: string | null;
  created_at: string;
  updated_at: string;
}

// --- Conversation ---
export interface ConversationCreate {
  title?: string | null;
}

export interface ConversationUpdate {
  title?: string | null;
}

export interface ConversationRead {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

// --- Message ---
export type MessageRole = "user" | "assistant" | "system";

export interface MessageRead {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface ChatSendRequest {
  conversation_id?: string | null;
  content: string;
  model?: string | null;
}

// --- Specification ---
export type SpecStatus = "draft" | "in_review" | "approved";

export interface SpecRead {
  id: string;
  conversation_id: string;
  title: string;
  content: string;
  status: SpecStatus;
  created_at: string;
  updated_at: string;
}

export interface SpecUpdate {
  title?: string | null;
  status?: SpecStatus | null;
  content?: string | null;
}

export interface SpecExtractRequest {
  model?: string | null;
}

// --- Design ---
export type DesignStatus = "draft" | "in_review" | "approved";

export interface DesignRead {
  id: string;
  conversation_id: string;
  specification_id: string;
  title: string;
  content: string;
  status: DesignStatus;
  created_at: string;
  updated_at: string;
}

export interface DesignUpdate {
  title?: string | null;
  status?: DesignStatus | null;
  content?: string | null;
}

export interface DesignDecomposeRequest {
  spec_id: string;
  model?: string | null;
}

// --- Decision ---
export type DecisionStatus = "pending" | "resolved" | "dismissed";

export interface DecisionOptionRead {
  id: string;
  label: string;
  description: string | null;
  pros: string[];
  cons: string[];
  sort_order: number;
}

export interface DecisionPointRead {
  id: string;
  conversation_id: string;
  design_id: string | null;
  question: string;
  context: string;
  recommendation: string | null;
  status: DecisionStatus;
  resolved_option_id: string | null;
  resolution_note: string | null;
  options: DecisionOptionRead[];
  created_at: string;
  updated_at: string;
}

export interface DecisionPointUpdate {
  status?: DecisionStatus | null;
  resolved_option_id?: string | null;
  resolution_note?: string | null;
}

export interface DecisionDetectRequest {
  model?: string | null;
}

// --- Generated Task ---
export type TaskPriority = "low" | "medium" | "high" | "critical";
export type TaskStatus = "pending" | "in_progress" | "done" | "skipped";

export interface GeneratedTaskRead {
  id: string;
  conversation_id: string;
  design_id: string;
  title: string;
  description: string;
  priority: TaskPriority;
  status: TaskStatus;
  dependencies: string[];
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface GeneratedTaskUpdate {
  title?: string | null;
  description?: string | null;
  priority?: TaskPriority | null;
  status?: TaskStatus | null;
}

export interface TaskGenerateRequest {
  design_id: string;
  model?: string | null;
}

// --- Generated Code ---
export type CodeStatus = "draft" | "approved" | "rejected";

export interface GeneratedCodeRead {
  id: string;
  conversation_id: string;
  task_id: string;
  content: string;
  status: CodeStatus;
  created_at: string;
  updated_at: string;
}

export interface GeneratedCodeUpdate {
  content?: string | null;
  status?: CodeStatus | null;
}

export interface CodeGenerateRequest {
  task_id: string;
  model?: string | null;
}

// --- Pull Request ---
export type PRStatus = "creating" | "created" | "merged" | "closed" | "failed";

export interface PullRequestRead {
  id: string;
  conversation_id: string;
  code_id: string;
  pr_number: number | null;
  pr_url: string | null;
  branch_name: string;
  title: string;
  description: string;
  status: PRStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface PullRequestUpdate {
  status?: PRStatus | null;
}

export interface PRCreateRequest {
  code_id: string;
}

// --- SSE Events ---
export interface SSEMessageSaved {
  conversation_id: string;
  message_id: string;
}

export interface SSEToken {
  content: string;
}

export interface SSEDone {
  conversation_id: string;
  message_id: string;
}

export interface SSEError {
  detail: string;
}

export interface SSEExtractionStarted {
  conversation_id: string;
  spec_id: string | null;
  mode: "create" | "update";
}

export interface SSEDetectionStarted {
  conversation_id: string;
}

export interface SSEDecomposeStarted {
  conversation_id: string;
  spec_id: string;
  design_id: string | null;
  mode: "create" | "update";
}

export interface SSEDesignSaved {
  design_id: string;
  conversation_id: string;
}

export interface SSEDesignDone {
  design_id: string;
  conversation_id: string;
  decision_count: number;
}

export interface SSEDecisionDone {
  conversation_id: string;
  count: number;
  decision_point_ids: string[];
}

export interface SSEGenerationStarted {
  conversation_id: string;
  design_id: string;
}

export interface SSETaskFound {
  task: GeneratedTaskRead;
}

export interface SSETaskDone {
  conversation_id: string;
  design_id: string;
  task_count: number;
}
