/* ============================================================
   Aegis · Sample data
   ------------------------------------------------------------
   Static demo data used to render the UI before (or without) a
   live backend. The eight governance actions mirror the action
   categories defined in the capstone report; the decision logs
   are illustrative examples for the History page. When the team
   wires up Supabase later, these arrays are simply replaced by
   API calls returning the same shapes (see types/index.ts).
   ============================================================ */

import type { GovernanceAction, DecisionLog, PendingAction } from "../types";

/**
 * The assistant's governable capabilities, grouped by risk.
 *
 * `survey` holds the user-survey results (96 respondents) for each action,
 * as percentages choosing Automatic / Approval Required / Locked. The
 * `defaultMode` is the majority answer from that survey. To update with new
 * survey numbers later, just edit the `survey` values and `defaultMode` here.
 */
export const governanceActions: GovernanceAction[] = [
  {
    id: 1,
    action: "Normal Chat",
    description: "Everyday conversation and simple, safe replies.",
    risk: "Low",
    mode: "Automatic",
    defaultMode: "Automatic",
    // Not part of the survey: baseline chat is automatic by design.
  },
  {
    id: 2,
    action: "Book or Reschedule Meeting",
    description: "Check availability and propose calendar changes.",
    risk: "Medium",
    mode: "Approval Required",
    defaultMode: "Approval Required",
    // Survey average of "book a meeting" and "reschedule a meeting".
    survey: { automatic: 21, approval: 58, locked: 21 },
  },
  {
    id: 3,
    action: "Forward Message to Contact",
    description: "Relay a message to an approved contact on your behalf.",
    risk: "Medium",
    mode: "Approval Required",
    defaultMode: "Approval Required",
    // Survey: "send a message to someone on your behalf".
    survey: { automatic: 32, approval: 52, locked: 16 },
  },
  {
    id: 4,
    action: "Send Non-Sensitive File",
    description: "Share a file that has been checked as non-sensitive.",
    risk: "Medium",
    mode: "Approval Required",
    defaultMode: "Approval Required",
    // Survey: "send a file to someone".
    survey: { automatic: 19, approval: 48, locked: 33 },
  },
  {
    id: 5,
    action: "Money Request",
    description: "Any message involving payments or transfers.",
    risk: "High",
    mode: "Locked",
    defaultMode: "Locked",
    // Survey average of "send money" and "approve a payment".
    survey: { automatic: 3, approval: 29, locked: 68 },
  },
  {
    id: 6,
    action: "Agreement Confirmation",
    description: "Confirming contracts or binding commitments.",
    risk: "High",
    mode: "Locked",
    defaultMode: "Locked",
    // Survey: "sign or accept a contract on your behalf".
    survey: { automatic: 3, approval: 29, locked: 68 },
  },
  {
    id: 7,
    action: "Emergency Response",
    description: "Replying to urgent or emergency situations.",
    risk: "High",
    mode: "Locked",
    defaultMode: "Locked",
    // Survey: "respond to an emergency situation".
    survey: { automatic: 18, approval: 21, locked: 61 },
  },
  {
    id: 8,
    action: "Send Sensitive File",
    description: "Sharing files flagged as private or sensitive.",
    risk: "High",
    mode: "Locked",
    defaultMode: "Locked",
    // Not surveyed separately (only generic "send a file" was); locked is the
    // safe default for sensitive data.
  },
];

/** Actions awaiting the user's approval, shown on the Approvals page. */
export const pendingApprovals: PendingAction[] = [
  {
    id: 1,
    contact: "Boss",
    message: "Can we move our 3 PM sync to tomorrow morning instead?",
    intent: "Book or Reschedule Meeting",
    risk: "Medium",
    proposed:
      "Reschedule the meeting to tomorrow at 09:30 and send a confirmation message.",
    time: "2 minutes ago",
  },
  {
    id: 2,
    contact: "Mom",
    message: "Tell your brother to call me when he gets a chance.",
    intent: "Forward Message to Contact",
    risk: "Medium",
    proposed:
      'Forward to Omar (approved contact): "Mom asked you to call her when you are free."',
    time: "18 minutes ago",
  },
  {
    id: 3,
    contact: "Teacher",
    message: "Could you send me the project brief you mentioned?",
    intent: "Send Non-Sensitive File",
    risk: "Medium",
    proposed: "Send file project-brief.pdf (scanned and marked non-sensitive).",
    time: "1 hour ago",
  },
  {
    id: 4,
    contact: "Friend",
    message: "Are you free for a quick call this evening around 8?",
    intent: "Book or Reschedule Meeting",
    risk: "Medium",
    proposed: "Add a call to the calendar for today at 20:00 and reply to confirm.",
    time: "3 hours ago",
  },
  {
    id: 5,
    contact: "Client",
    message: "Please transfer $200 to this account today.",
    intent: "Money Request",
    risk: "High",
    proposed: "Send $200 to the account ending 4471.",
    time: "6 minutes ago",
  },
  {
    id: 6,
    contact: "Client",
    message: "Can you send me the signed contract PDF?",
    intent: "Send Sensitive File",
    risk: "High",
    proposed: "Send file contract-signed.pdf (flagged sensitive).",
    time: "35 minutes ago",
  },
];

/** Recent decisions for the History page. */
export const decisionLogs: DecisionLog[] = [
  {
    id: 1,
    message: "Can we reschedule our meeting to tomorrow?",
    contact: "Boss",
    intent: "Book or Reschedule Meeting",
    risk: "Medium",
    decision: "Approval requested",
    time: "Today, 09:24",
  },
  {
    id: 2,
    message: "Can you send me the signed contract?",
    contact: "Client",
    intent: "Send Sensitive File",
    risk: "High",
    decision: "Blocked until approval",
    time: "Today, 08:57",
  },
  {
    id: 3,
    message: "Thanks, that works for me!",
    contact: "Friend",
    intent: "Normal Chat",
    risk: "Low",
    decision: "Auto-replied",
    time: "Yesterday, 19:40",
  },
  {
    id: 4,
    message: "Please ask John to call me back.",
    contact: "Mom",
    intent: "Forward Message to Contact",
    risk: "Medium",
    decision: "Approval requested",
    time: "Yesterday, 15:12",
  },
  {
    id: 5,
    message: "Send 200 to my account now.",
    contact: "Unknown",
    intent: "Money Request",
    risk: "High",
    decision: "Blocked until approval",
    time: "Yesterday, 11:03",
  },
  {
    id: 6,
    message: "Sounds good, see you then.",
    contact: "Sister",
    intent: "Normal Chat",
    risk: "Low",
    decision: "Auto-replied",
    time: "Mon, 22:18",
  },
];
