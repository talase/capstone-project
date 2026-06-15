/* ============================================================
   Aegis · Personal Context page
   ------------------------------------------------------------
   Lets the user write a short "personal context" note that the
   assistant uses as background when it replies on their behalf
   (e.g. "Travelling until Monday, keep replies brief"). The note
   is loaded from, saved to, and cleared on the backend's
   /personal-context/status endpoint. The backend uses the literal
   value "available" to mean "no context set", so we map that to an
   empty field here.
   ============================================================ */

import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import {
  getPersonalContext,
  savePersonalContext,
  clearPersonalContext,
  ApiError,
} from "../services/api";
import styles from "./PersonalContext.module.css";

const MAX = 2000;
const AVAILABLE = "available"; // backend sentinel for "no context set"

function PersonalContext() {
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState(""); // last saved context ("" = none)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Load the currently saved context on first render.
  useEffect(() => {
    let active = true;
    getPersonalContext()
      .then((status) => {
        if (!active) return;
        const value = status.status === AVAILABLE ? "" : status.status;
        setSaved(value);
        setDraft(value);
        setUpdatedAt(status.updated_at ?? status.created_at ?? null);
      })
      .catch((err) => active && setError(messageFor(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const trimmed = draft.trim();
  const dirty = trimmed !== saved.trim();

  async function handleSave() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await savePersonalContext(trimmed);
      const value = result.status === AVAILABLE ? "" : result.status;
      setSaved(value);
      setDraft(value);
      setUpdatedAt(result.updated_at ?? result.created_at ?? null);
      setNotice("Personal context saved.");
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleClear() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await clearPersonalContext();
      setSaved("");
      setDraft("");
      setUpdatedAt(null);
      setNotice("Personal context cleared.");
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Personal Context"
        subtitle="A short note about your current situation that the assistant uses as context when it replies on your behalf — for example, “Travelling until Monday, keep replies brief.”"
      />

      <Card
        title="Your context memory"
        subtitle="Stored on the backend and applied to every governed reply."
      >
        {loading ? (
          <p className={styles.muted}>Loading your saved context…</p>
        ) : (
          <>
            <textarea
              className={styles.textarea}
              value={draft}
              maxLength={MAX}
              rows={6}
              placeholder="e.g. I'm a final-year student at BAU. I prefer short, polite replies. I'm on holiday until June 20th."
              onChange={(event) => setDraft(event.target.value)}
              disabled={busy}
            />

            <div className={styles.meta}>
              <span className={styles.count}>
                {draft.length} / {MAX}
              </span>
              {updatedAt && (
                <span className={styles.muted}>
                  Last saved: {formatTime(updatedAt)}
                </span>
              )}
            </div>

            {error && <p className={styles.error}>{error}</p>}
            {notice && !error && <p className={styles.notice}>{notice}</p>}

            <div className={styles.actions}>
              <button
                className={styles.secondary}
                onClick={handleClear}
                disabled={busy || (!saved && !trimmed)}
              >
                Clear
              </button>
              <button
                className={styles.primary}
                onClick={handleSave}
                disabled={busy || !trimmed || !dirty}
              >
                {busy ? "Saving…" : "Save context"}
              </button>
            </div>
          </>
        )}
      </Card>
    </>
  );
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503)
      return "The backend can't reach its database (Supabase isn't configured). Start the backend with valid Supabase keys to save context.";
    return err.message;
  }
  return "Something went wrong. Please try again.";
}

function formatTime(value: string): string {
  const date = new Date(value);
  return isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default PersonalContext;
