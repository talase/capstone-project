/* ============================================================
   Aegis · Shared types
   ------------------------------------------------------------
   Central place for the TypeScript types used across the app.
   Keeping them in one file means every component agrees on the
   exact shape of the data (a GovernanceAction always has the same
   fields everywhere), and the compiler catches mismatches for us.
   ============================================================ */

/** How risky an assistant action is considered to be. */
export type RiskLevel = "Low" | "Medium" | "High";
export type ActionRiskLevel = "low" | "medium" | "high";

/**
 * How the assistant is allowed to perform an action:
 *  - Automatic         → done immediately, no human needed
 *  - Approval Required → proposed, but waits for the user to confirm
 *  - Locked            → never automated; always blocked until approval
 */
export type AutomationMode = "Automatic" | "Approval Required" | "Locked";

/** A single governable capability of the assistant (e.g. "Send File"). */
export interface GovernanceAction {
  id: number;
  action: string;              // human-readable name
  description: string;         // what it does
  risk: RiskLevel;
  mode: AutomationMode;         // the currently selected mode
  defaultMode: AutomationMode;  // survey-recommended default: marks the default option and is restored on reset
  /**
   * How users answered the risk survey for this action, as percentages
   * (automatic + approval + locked add up to ~100). Optional because a
   * couple of actions were not in the survey. The default above is the
   * majority answer here.
   */
  survey?: { automatic: number; approval: number; locked: number };
}

/**
 * An action the assistant has proposed and is waiting on the user to
 * approve. These are the medium-risk items that the Governance page has
 * set to "Approval Required" — they appear on the Approvals page until
 * the user approves or rejects them.
 */
export interface PendingAction {
  id: number;
  contact: string;   // who the conversation is with
  message: string;   // the incoming message that triggered the action
  intent: string;    // the detected action category
  risk: RiskLevel;
  proposed: string;  // a plain-language summary of what the assistant wants to do
  time: string;      // when it was requested (display string)
}

/** A past decision the assistant made, shown on the History page. */
export interface DecisionLog {
  id: number;
  message: string;   // the incoming message
  contact: string;   // who it came from
  intent: string;    // detected intent / action category
  risk: RiskLevel;
  decision: string;  // what the governance layer decided
  time: string;      // when it happened (display string)
}

/* ---- Backend-connected features ------------------------------------------ */

/**
 * The user's Personal Context Memory as stored by the backend
 * (`/personal-context/status`). `status` is a free-text note the assistant
 * uses as context (e.g. "On holiday until Monday"); the backend treats the
 * literal value "available" as "no special context set".
 */
export interface UserStatus {
  id?: number | string | null;
  user_id: string;
  status: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Result returned by the backend after a successful dashboard file upload. */
export interface UploadResult {
  success: boolean;
  file_name: string;
  storage_path: string;
  message: string;
}

/** A file persisted in the dashboard folder of Supabase Storage. */
export interface DashboardStoredFile {
  file_name: string;
  storage_path: string;
  is_sensitive: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  size?: number | null;
  content_type?: string | null;
}

/** A contact stored by the backend's contacts API. */
export interface Contact {
  id: string;
  name: string;
  phone_number: string;
  relationship_type?: string | null;
  notes?: string | null;
  can_receive_requested_messages: boolean;
  message_aliases?: string[] | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Fields accepted by POST /contacts and PATCH /contacts/{contact_id}. */
export interface ContactInput {
  name: string;
  phone_number: string;
  relationship_type?: string | null;
  notes?: string | null;
  can_receive_requested_messages: boolean;
  message_aliases?: string[] | null;
}

/** One row from the backend action_settings table. */
export interface ActionSetting {
  id: string;
  user_id: string;
  action_type: string;
  risk_level: ActionRiskLevel;
  is_editable: boolean;
  description?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** A recent row from the messages table, enriched with the contact name. */
export interface MessageHistoryItem {
  id: string;
  message_text: string;
  contact_id?: string | null;
  contact_name: string;
  direction: string;
  predicted_actions: string[];
  risk_level?: ActionRiskLevel | null;
  status?: string | null;
  confidence?: number | null;
  created_at: string;
}

/** One approvals row enriched by the backend with related record labels. */
export interface DashboardApproval {
  id: string;
  message_id?: string | null;
  contact_id?: string | null;
  action_type: string;
  risk_level?: ActionRiskLevel | null;
  status: string;
  file_id?: string | null;
  phone_number?: string | null;
  approval_message?: string | null;
  target_contact_id?: string | null;
  target_contact_name?: string | null;
  message_to_send?: string | null;
  request_text?: string | null;
  proposed_response?: string | null;
  user_edited_response?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  requester_name: string;
  requester_phone_number?: string | null;
  source_message_text?: string | null;
  source_message_direction?: string | null;
  source_message_created_at?: string | null;
  file_name?: string | null;
  file_storage_path?: string | null;
  file_type?: string | null;
  file_is_sensitive?: boolean | null;
  target_contact_phone_number?: string | null;
}

export interface DashboardActionCount {
  action_type: string;
  count: number;
}

/** Aggregate live counts returned by GET /dashboard-summary. */
export interface DashboardSummary {
  approvals_total: number;
  approvals_pending: number;
  approvals_approved: number;
  approvals_rejected: number;
  approvals_executed: number;
  approvals_blocked: number;
  messages_total: number;
  incoming_messages: number;
  outgoing_messages: number;
  contacts_total: number;
  uploaded_files_total: number;
  sensitive_files: number;
  non_sensitive_files: number;
  actions_by_type: DashboardActionCount[];
}
