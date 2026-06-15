import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "../components/Badge";
import { PageHeader } from "../components/PageHeader";
import { CheckIcon, FileIcon, InboxIcon } from "../components/icons";
import { ApiError, getDashboardApprovals } from "../services/api";
import type { DashboardApproval } from "../types";
import styles from "./Approvals.module.css";

type Filter =
  | "pending"
  | "all"
  | "approved"
  | "rejected"
  | "executed"
  | "blocked_high_risk";
const filters: { value: Filter; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "all", label: "All" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "executed", label: "Executed" },
  { value: "blocked_high_risk", label: "Blocked" },
];

function Approvals() {
  const [approvals, setApprovals] = useState<DashboardApproval[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadApprovals = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    setError(null);
    try {
      setApprovals(await getDashboardApprovals());
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getDashboardApprovals()
      .then((items) => {
        if (active) setApprovals(items);
      })
      .catch((err) => {
        if (active) setError(messageFor(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleApprovals = useMemo(
    () =>
      filter === "all"
        ? approvals
        : approvals.filter((approval) => approval.status === filter),
    [approvals, filter]
  );
  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Read-only approval records with related contacts, messages, and files."
        action={
          <div className={styles.headerActions}>
            <span className={styles.counter}>
              <InboxIcon size={16} />
              {approvals.length} records
            </span>
            <button
              className={styles.refresh}
              onClick={() => void loadApprovals(true)}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        }
      />

      <div className={styles.filters}>
        {filters.map((item) => (
          <button
            key={item.value}
            className={`${styles.filter} ${
              filter === item.value ? styles.activeFilter : ""
            }`}
            onClick={() => setFilter(item.value)}
          >
            {item.label}
            <span>{statusCount(approvals, item.value)}</span>
          </button>
        ))}
      </div>

      {error && <p className={styles.error}>{error}</p>}

      {loading ? (
        <div className={styles.empty}>Loading approvals...</div>
      ) : visibleApprovals.length === 0 ? (
        <div className={styles.empty}>
          <span className={styles.emptyMark}>
            <CheckIcon size={26} />
          </span>
          <p>
            {filter === "all"
              ? "No approval records found."
              : `No ${formatLabel(filter)} approval records found.`}
          </p>
        </div>
      ) : (
        <div className={styles.list}>
          {visibleApprovals.map((approval) => (
            <ApprovalCard key={approval.id} approval={approval} />
          ))}
        </div>
      )}
    </>
  );
}

function ApprovalCard({ approval }: { approval: DashboardApproval }) {
  const requestMessage =
    approval.source_message_text ??
    approval.request_text ??
    approval.approval_message ??
    "No request message was stored.";
  return (
    <article className={styles.card}>
      <header className={styles.cardHead}>
        <div>
          <div className={styles.titleLine}>
            <h2>{approval.requester_name}</h2>
            <Badge tone={approval.risk_level ?? "neutral"}>
              {approval.risk_level
                ? formatLabel(approval.risk_level)
                : "Risk not set"}
            </Badge>
            <span
              className={`${styles.status} ${
                styles[statusClass(approval.status)]
              }`}
            >
              {formatLabel(approval.status)}
            </span>
          </div>
          <p className={styles.contactLine}>
            {approval.requester_phone_number ??
              approval.phone_number ??
              "No phone number"}
            {" · "}
            {formatTime(approval.created_at)}
          </p>
        </div>
        <span className={styles.actionType}>
          {formatLabel(approval.action_type)}
        </span>
      </header>

      <section className={styles.request}>
        <span>Request message</span>
        <p>{requestMessage}</p>
      </section>

      <div className={styles.details}>
        <Detail label="Requester">
          {approval.requester_name}
          {approval.contact_id && <code>{approval.contact_id}</code>}
        </Detail>
        <Detail label="Source message">
          {approval.source_message_direction
            ? formatLabel(approval.source_message_direction)
            : "No linked message"}
          {approval.message_id && <code>{approval.message_id}</code>}
        </Detail>
        {approval.target_contact_name && (
          <Detail label="Target contact">
            {approval.target_contact_name}
            {approval.target_contact_phone_number && (
              <small>{approval.target_contact_phone_number}</small>
            )}
            {approval.target_contact_id && (
              <code>{approval.target_contact_id}</code>
            )}
          </Detail>
        )}
        {approval.file_id && (
          <Detail label="Related file">
            <span className={styles.fileName}>
              <FileIcon size={14} />
              {approval.file_name ?? "File record not found"}
            </span>
            <small>
              {[
                approval.file_type?.toUpperCase(),
                approval.file_is_sensitive === true
                  ? "Sensitive"
                  : approval.file_is_sensitive === false
                    ? "Not sensitive"
                    : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </small>
            <code>{approval.file_id}</code>
          </Detail>
        )}
      </div>

      {approval.approval_message &&
        approval.approval_message !== requestMessage && (
          <TextBlock label="Approval message" value={approval.approval_message} />
        )}
      {(approval.user_edited_response ??
        approval.message_to_send ??
        approval.proposed_response) && (
        <TextBlock
          label={
            approval.user_edited_response
              ? "User-edited message"
              : "Message to send"
          }
          value={
            approval.user_edited_response ??
            approval.message_to_send ??
            approval.proposed_response ??
            ""
          }
        />
      )}

      <footer className={styles.cardFooter}>
        <span>
          Approval ID <code>{approval.id}</code>
          {approval.resolved_at && (
            <> · Resolved {formatTime(approval.resolved_at)}</>
          )}
        </span>
      </footer>
    </article>
  );
}

function Detail({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.detail}>
      <span>{label}</span>
      <div>{children}</div>
    </div>
  );
}

function TextBlock({ label, value }: { label: string; value: string }) {
  return (
    <section className={styles.textBlock}>
      <span>{label}</span>
      <p>{value}</p>
    </section>
  );
}

function statusCount(approvals: DashboardApproval[], filter: Filter): number {
  return filter === "all"
    ? approvals.length
    : approvals.filter((approval) => approval.status === filter).length;
}

function statusClass(status: string): string {
  if (status === "pending") return "statusPending";
  if (status === "approved" || status === "executed") return "statusPositive";
  return "statusNegative";
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTime(value?: string | null): string {
  if (!value) return "Time not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Could not load approvals. Please try again.";
}

export default Approvals;
