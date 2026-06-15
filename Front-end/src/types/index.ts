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
