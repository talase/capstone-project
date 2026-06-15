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

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DragEvent,
} from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { UploadIcon, FileIcon } from "../components/icons";
import {
  ApiError,
  deleteDashboardFile,
  downloadDashboardFile,
  getDashboardFiles,
  uploadDashboardFile,
} from "../services/api";
import type { DashboardStoredFile } from "../types";
import styles from "./UploadFiles.module.css";

function UploadFiles() {
  const [file, setFile] = useState<File | null>(null);
  const [sensitive, setSensitive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [storedFiles, setStoredFiles] = useState<DashboardStoredFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] =
    useState<DashboardStoredFile | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const refreshFiles = useCallback(async () => {
    setFilesError(null);
    try {
      setStoredFiles(await getDashboardFiles());
    } catch (err) {
      setFilesError(messageFor(err));
    } finally {
      setLoadingFiles(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getDashboardFiles()
      .then((files) => {
        if (active) setStoredFiles(files);
      })
      .catch((err) => {
        if (active) setFilesError(messageFor(err));
      })
      .finally(() => {
        if (active) setLoadingFiles(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function pick(selected: File | null) {
    setFile(selected);
    setError(null);
  }

  async function handleUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadDashboardFile(file, sensitive);
      setFile(null);
      setSensitive(false);
      if (inputRef.current) inputRef.current.value = "";
      await refreshFiles();
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

  async function handleDownload(item: DashboardStoredFile) {
    setDownloading(item.storage_path);
    setFilesError(null);
    try {
      const blob = await downloadDashboardFile(item.storage_path);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = item.file_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setFilesError(messageFor(err));
    } finally {
      setDownloading(null);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    setDeleting(true);
    setFilesError(null);
    try {
      await deleteDashboardFile(deleteTarget.storage_path);
      setStoredFiles((current) =>
        current.filter(
          (item) => item.storage_path !== deleteTarget.storage_path
        )
      );
      setDeleteTarget(null);
    } catch (err) {
      setFilesError(messageFor(err));
    } finally {
      setDeleting(false);
    }
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

      <Card
        title="Stored files"
        subtitle="Files saved in Supabase remain available after you leave or refresh this page."
        action={
          <button
            className={styles.secondary}
            onClick={() => void refreshFiles()}
            disabled={loadingFiles}
          >
            Refresh
          </button>
        }
      >
        {loadingFiles ? (
          <p className={styles.muted}>Loading stored files...</p>
        ) : filesError ? (
          <p className={styles.error}>{filesError}</p>
        ) : storedFiles.length === 0 ? (
          <p className={styles.muted}>No dashboard files have been uploaded yet.</p>
        ) : (
          <ul className={styles.list}>
            {storedFiles.map((item) => (
              <li key={item.storage_path} className={styles.row}>
                <div className={styles.fileInfo}>
                  <span className={styles.rowName}>
                    <FileIcon size={15} />
                    {item.file_name}
                    {item.is_sensitive && <Badge tone="high">Sensitive</Badge>}
                  </span>
                  <span className={styles.details}>
                    {item.size != null && formatSize(item.size)}
                    {item.size != null && item.created_at && " · "}
                    {item.created_at && formatTime(item.created_at)}
                  </span>
                </div>
                <div className={styles.rowActions}>
                  <button
                    className={styles.download}
                    onClick={() => void handleDownload(item)}
                    disabled={downloading === item.storage_path}
                  >
                    {downloading === item.storage_path
                      ? "Downloading..."
                      : "Download"}
                  </button>
                  <button
                    className={styles.delete}
                    onClick={() => setDeleteTarget(item)}
                  >
                    Delete
                  </button>
                </div>
                <span className={styles.path}>{item.storage_path}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {deleteTarget && (
        <Modal title="Delete stored file" onClose={() => setDeleteTarget(null)}>
          <p className={styles.dialogText}>
            Permanently delete <strong>{deleteTarget.file_name}</strong> from
            Supabase Storage? This cannot be undone.
          </p>
          <div className={styles.dialogActions}>
            <button
              className={styles.secondary}
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Cancel
            </button>
            <button
              className={styles.deleteSolid}
              onClick={() => void handleDelete()}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete file"}
            </button>
          </div>
        </Modal>
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

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default UploadFiles;
