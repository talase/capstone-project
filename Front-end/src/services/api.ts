/* ============================================================
   Aegis · Backend API client
   ------------------------------------------------------------
   Thin wrapper around the team's FastAPI backend for the two
   dashboard-connected features:
     - Personal Context Memory  -> /personal-context/status
     - File upload              -> /files/upload-dashboard

   In development these are reached through the Vite dev proxy
   (see vite.config.ts), so the browser stays same-origin and no
   backend CORS change is needed. Set VITE_API_BASE_URL to call an
   absolute backend URL instead (e.g. in production).
   ============================================================ */

import type {
  ActionRiskLevel,
  ActionSetting,
  Contact,
  ContactInput,
  DashboardApproval,
  DashboardSummary,
  DashboardStoredFile,
  MessageHistoryItem,
  ScheduleMessageInput,
  ScheduleMessageResult,
  UserStatus,
  UploadResult,
} from "../types";

// Empty base => same-origin (the Vite proxy forwards to the backend).
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const CONTACTS_PATH = API_BASE ? "/contacts" : "/api/contacts";
const ACTION_SETTINGS_PATH = API_BASE
  ? "/action-settings"
  : "/api/action-settings";
const MESSAGE_HISTORY_PATH = API_BASE
  ? "/message-history"
  : "/api/message-history";
const DASHBOARD_APPROVALS_PATH = API_BASE
  ? "/dashboard-approvals"
  : "/api/dashboard-approvals";
const DASHBOARD_SUMMARY_PATH = API_BASE
  ? "/dashboard-summary"
  : "/api/dashboard-summary";
const SCHEDULE_MESSAGE_PATH = API_BASE
  ? "/schedule-message"
  : "/api/schedule-message";

// The backend keys context/status by user id; the demo uses its default user.
const USER_ID = "default_user";

/** Error that carries the HTTP status so the UI can show a clear message. */
export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Pull a human-readable message out of a failed response. */
async function readError(response: Response): Promise<string> {
  // Prefer the backend's own message if it sent one.
  let detail = "";
  try {
    const body = await response.json();
    if (body?.detail) detail = String(body.detail);
    else if (body?.error) detail = String(body.error);
  } catch {
    /* response had no JSON body */
  }
  if (detail) return detail;

  // No body: usually the dev proxy couldn't reach the backend.
  if (response.status === 502 || response.status === 504) {
    return "Could not reach the backend. Is it running on the configured port?";
  }
  if (response.status === 404) {
    return "Endpoint not found (404). The backend 'files' router may still be disabled in main.py.";
  }
  return `Request failed (${response.status})`;
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Could not reach the backend. Is it running?");
  }
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return (await response.json()) as T;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

/* ---- Personal Context Memory --------------------------------------------- */

/** Read the user's currently saved context (status). */
export function getPersonalContext(): Promise<UserStatus> {
  return requestJson(
    `/personal-context/status?user_id=${encodeURIComponent(USER_ID)}`,
    { method: "GET" }
  );
}

/** Save (create or replace) the user's personal context. */
export function savePersonalContext(status: string): Promise<UserStatus> {
  return requestJson(`/personal-context/status`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ user_id: USER_ID, status }),
  });
}

/** Clear the context (the backend resets it to "available"). */
export function clearPersonalContext(): Promise<UserStatus> {
  return requestJson(
    `/personal-context/status?user_id=${encodeURIComponent(USER_ID)}`,
    { method: "DELETE" }
  );
}

/* ---- File upload --------------------------------------------------------- */

/** Upload one file to the backend (Supabase storage + n8n ingestion). */
export async function uploadDashboardFile(
  file: File,
  isSensitive: boolean
): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("is_sensitive", String(isSensitive));

  let response: Response;
  try {
    // No Content-Type header — the browser sets the multipart boundary itself.
    response = await fetch(`${API_BASE}/files/upload-dashboard`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError("Could not reach the backend. Is it running?");
  }
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return (await response.json()) as UploadResult;
}

/** List files that remain available in the dashboard's Supabase folder. */
export function getDashboardFiles(): Promise<DashboardStoredFile[]> {
  return requestJson("/files/dashboard-uploads", { method: "GET" });
}

/** Download one persisted dashboard file through the backend. */
export async function downloadDashboardFile(
  storagePath: string
): Promise<Blob> {
  let response: Response;
  try {
    const query = new URLSearchParams({ storage_path: storagePath });
    response = await fetch(
      `${API_BASE}/files/dashboard-download?${query.toString()}`
    );
  } catch {
    throw new ApiError("Could not reach the backend. Is it running?");
  }
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return response.blob();
}

/** Permanently delete one file from the dashboard's Supabase folder. */
export function deleteDashboardFile(
  storagePath: string
): Promise<{ storage_path: string; message: string }> {
  const query = new URLSearchParams({ storage_path: storagePath });
  return requestJson(`/files/dashboard-upload?${query.toString()}`, {
    method: "DELETE",
  });
}

/* ---- Contacts ------------------------------------------------------------ */

export function getContacts(): Promise<Contact[]> {
  return requestJson(CONTACTS_PATH, { method: "GET" });
}

export function createContact(contact: ContactInput): Promise<Contact> {
  return requestJson(CONTACTS_PATH, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(contact),
  });
}

export function updateContact(
  contactId: string,
  contact: ContactInput
): Promise<Contact> {
  return requestJson(`${CONTACTS_PATH}/${encodeURIComponent(contactId)}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(contact),
  });
}

export function deleteContact(
  contactId: string
): Promise<{ message: string }> {
  return requestJson(`${CONTACTS_PATH}/${encodeURIComponent(contactId)}`, {
    method: "DELETE",
  });
}

/* ---- Action settings ----------------------------------------------------- */

export function getActionSettings(): Promise<ActionSetting[]> {
  const query = new URLSearchParams({ user_id: USER_ID });
  return requestJson(`${ACTION_SETTINGS_PATH}?${query.toString()}`, {
    method: "GET",
  });
}

export function updateActionSetting(
  settingId: string,
  riskLevel: ActionRiskLevel
): Promise<ActionSetting> {
  const query = new URLSearchParams({ user_id: USER_ID });
  return requestJson(
    `${ACTION_SETTINGS_PATH}/${encodeURIComponent(settingId)}?${query.toString()}`,
    {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify({ risk_level: riskLevel }),
    }
  );
}

/* ---- Message history ----------------------------------------------------- */

export function getMessageHistory(limit = 100): Promise<MessageHistoryItem[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  return requestJson(`${MESSAGE_HISTORY_PATH}?${query.toString()}`, {
    method: "GET",
  });
}

/* ---- Approvals ----------------------------------------------------------- */

export function getDashboardApprovals(
  limit = 200
): Promise<DashboardApproval[]> {
  const query = new URLSearchParams({
    user_id: USER_ID,
    limit: String(limit),
  });
  return requestJson(`${DASHBOARD_APPROVALS_PATH}?${query.toString()}`, {
    method: "GET",
  });
}

/* ---- Dashboard summary --------------------------------------------------- */

export function getDashboardSummary(): Promise<DashboardSummary> {
  const query = new URLSearchParams({ user_id: USER_ID });
  return requestJson(`${DASHBOARD_SUMMARY_PATH}?${query.toString()}`, {
    method: "GET",
  });
}

/* ---- Scheduled messages -------------------------------------------------- */

export function scheduleMessage(
  message: ScheduleMessageInput
): Promise<ScheduleMessageResult> {
  return requestJson(SCHEDULE_MESSAGE_PATH, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(message),
  });
}

export { API_BASE };
