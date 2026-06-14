/* ============================================================
   Aegis · Upload Files page
   ------------------------------------------------------------
   Lets the user send a document to the assistant's knowledge base.
   The file is posted to the backend's /files/upload-dashboard
   endpoint (multipart), which stores it and hands it to n8n for
   processing. A "sensitive" flag ties the upload into the same
   governance idea used elsewhere in the app. Successful uploads are
   listed for the current session.
   ============================================================ */

import { useRef, useState, type DragEvent } from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { UploadIcon, FileIcon, CheckIcon } from "../components/icons";
import { uploadDashboardFile, ApiError } from "../services/api";
import type { UploadResult } from "../types";
import styles from "./UploadFiles.module.css";

interface Uploaded {
  name: string;
  path: string;
  sensitive: boolean;
}

function UploadFiles() {
  const [file, setFile] = useState<File | null>(null);
  const [sensitive, setSensitive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Uploaded[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(selected: File | null) {
    setFile(selected);
    setError(null);
  }

  async function handleUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result: UploadResult = await uploadDashboardFile(file, sensitive);
      setDone((current) => [
        { name: result.file_name, path: result.storage_path, sensitive },
        ...current,
      ]);
      setFile(null);
      setSensitive(false);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) pick(dropped);
  }

  return (
    <>
      <PageHeader
        title="Upload Files"
        subtitle="Send a document to the assistant's knowledge base. Files are stored securely and processed so the assistant can reference them when it replies."
      />

      <Card title="Upload a file" subtitle="PDF, image, or document — one file at a time.">
        <div
          className={`${styles.drop} ${dragging ? styles.dropActive : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) =>
            (event.key === "Enter" || event.key === " ") &&
            inputRef.current?.click()
          }
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <span className={styles.dropMark}>
            <UploadIcon size={22} />
          </span>
          {file ? (
            <p className={styles.fileName}>
              <FileIcon size={15} /> {file.name}{" "}
              <span className={styles.size}>({formatSize(file.size)})</span>
            </p>
          ) : (
            <>
              <p className={styles.dropText}>
                <strong>Click to choose a file</strong> or drag it here
              </p>
              <span className={styles.muted}>Max one file per upload</span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            className={styles.hiddenInput}
            onChange={(event) => pick(event.target.files?.[0] ?? null)}
          />
        </div>

        <label className={styles.sensitive}>
          <input
            type="checkbox"
            checked={sensitive}
            onChange={(event) => setSensitive(event.target.checked)}
          />
          <span>
            Mark as <strong>sensitive</strong>
            <small>
              Sensitive files are flagged for stricter governance, the same way
              high-risk actions are.
            </small>
          </span>
        </label>

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.actions}>
          <button
            className={styles.primary}
            onClick={handleUpload}
            disabled={busy || !file}
          >
            <UploadIcon size={16} />
            {busy ? "Uploading…" : "Upload file"}
          </button>
        </div>
      </Card>

      {done.length > 0 && (
        <Card
          title="Uploaded this session"
          subtitle={`${done.length} file${done.length > 1 ? "s" : ""} sent for processing`}
        >
          <ul className={styles.list}>
            {done.map((item, index) => (
              <li key={index} className={styles.row}>
                <span className={styles.rowName}>
                  <span className={styles.ok}>
                    <CheckIcon size={14} />
                  </span>
                  <FileIcon size={15} />
                  {item.name}
                </span>
                {item.sensitive && <Badge tone="high">Sensitive</Badge>}
                <span className={styles.path}>{item.path}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503)
      return "The backend can't reach its file storage (Supabase isn't configured).";
    return err.message;
  }
  return "Upload failed. Please try again.";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default UploadFiles;
