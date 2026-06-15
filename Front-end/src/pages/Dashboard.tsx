import { useCallback, useEffect, useState } from "react";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import {
  FileIcon,
  HistoryIcon,
  InboxIcon,
  UsersIcon,
} from "../components/icons";
import { ApiError, getDashboardSummary } from "../services/api";
import type { DashboardSummary } from "../types";
import styles from "./Dashboard.module.css";

const approvalStatuses = [
  { key: "approvals_pending", label: "Pending" },
  { key: "approvals_approved", label: "Approved" },
  { key: "approvals_rejected", label: "Rejected" },
  { key: "approvals_executed", label: "Executed" },
  { key: "approvals_blocked", label: "Blocked high risk" },
] as const;

function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSummary = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      setSummary(await getDashboardSummary());
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getDashboardSummary()
      .then((data) => {
        if (active) setSummary(data);
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

  const value = (count?: number) => (loading ? "..." : (count ?? 0));

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Live activity and stored-data totals from the assistant."
        action={
          <button
            className={styles.refresh}
            onClick={() => void refreshSummary()}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        }
      />

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.stats}>
        <StatCard
          label="Incoming messages"
          value={value(summary?.incoming_messages)}
          accent="brand"
          icon={<InboxIcon />}
          hint="Direction is incoming in the messages table"
        />
        <StatCard
          label="Outgoing messages"
          value={value(summary?.outgoing_messages)}
          accent="low"
          icon={<HistoryIcon />}
          hint="Direction is outgoing in the messages table"
        />
        <StatCard
          label="Approval records"
          value={value(summary?.approvals_total)}
          accent="medium"
          icon={<InboxIcon />}
          hint={
            summary
              ? `${summary.approvals_pending} pending · ${summary.approvals_executed} executed`
              : "Rows in the approvals table"
          }
        />
        <StatCard
          label="Contacts"
          value={value(summary?.contacts_total)}
          accent="brand"
          icon={<UsersIcon />}
          hint="Saved contacts"
        />
        <StatCard
          label="Uploaded files"
          value={value(summary?.uploaded_files_total)}
          accent="high"
          icon={<FileIcon />}
          hint={
            summary
              ? `${summary.sensitive_files} sensitive · ${summary.non_sensitive_files} non-sensitive`
              : "Files in dashboard uploads"
          }
        />
      </div>

      <div className={styles.panels}>
        <Card
          title="Approval activity"
          subtitle="Current status totals from the approvals table."
        >
          <div className={styles.statusList}>
            {approvalStatuses.map((item) => {
              const count = summary?.[item.key] ?? 0;
              const total = summary?.approvals_total ?? 0;
              return (
                <div key={item.key} className={styles.statusRow}>
                  <div className={styles.statusMeta}>
                    <span>{item.label}</span>
                    <strong>{value(count)}</strong>
                  </div>
                  <div className={styles.track}>
                    <span
                      className={styles.fill}
                      style={{
                        width: `${total > 0 ? (count / total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title="Actions recorded"
          subtitle="Action types detected in the approvals table."
        >
          <div className={styles.actionList}>
            {(summary?.actions_by_type ?? []).map((action) => (
              <div key={action.action_type} className={styles.actionRow}>
                <span>{formatLabel(action.action_type)}</span>
                <strong>{action.count}</strong>
              </div>
            ))}
            {!loading && (summary?.actions_by_type.length ?? 0) === 0 && (
              <p className={styles.empty}>No approval actions recorded.</p>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Could not load the dashboard summary. Please try again.";
}

export default Dashboard;
