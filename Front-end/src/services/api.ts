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

import type { UserStatus, UploadResult } from "../types";

// Empty base => same-origin (the Vite proxy forwards to the backend).
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

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

export { API_BASE };
