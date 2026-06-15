import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { ApiError, getMessageHistory } from "../services/api";
import type {
  ActionRiskLevel,
  MessageHistoryItem,
} from "../types";
import styles from "./History.module.css";

type Filter = "all" | ActionRiskLevel;
const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

function History() {
  const [messages, setMessages] = useState<MessageHistoryItem[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      setMessages(await getMessageHistory());
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getMessageHistory()
      .then((items) => {
        if (active) setMessages(items);
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

  const rows = useMemo(
    () =>
      filter === "all"
        ? messages
        : messages.filter((message) => message.risk_level === filter),
    [filter, messages]
  );

  return (
    <>
      <PageHeader
        title="History"
        subtitle="Recent incoming and outgoing messages loaded from the messages table."
        action={
          <div className={styles.headerActions}>
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
                </button>
              ))}
            </div>
            <button
              className={styles.refresh}
              onClick={() => void refreshHistory()}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        }
      />

      <Card>
        {loading ? (
          <p className={styles.empty}>Loading message history...</p>
        ) : error && messages.length === 0 ? (
          <p className={styles.error}>{error}</p>
        ) : (
          <>
            {error && <p className={styles.error}>{error}</p>}
            <div className={styles.table}>
              <div className={`${styles.row} ${styles.head}`}>
                <span>Message</span>
                <span>Contact</span>
                <span>Direction</span>
                <span>Detected actions</span>
                <span>Risk</span>
                <span>Status</span>
                <span>Time</span>
              </div>

              {rows.map((message) => (
                <div key={message.id} className={styles.row}>
                  <span className={styles.message} data-label="Message">
                    {message.message_text || "Empty message"}
                  </span>
                  <span data-label="Contact">{message.contact_name}</span>
                  <span data-label="Direction">
                    <span className={styles.direction}>
                      {formatLabel(message.direction)}
                    </span>
                  </span>
                  <span className={styles.actions} data-label="Detected actions">
                    {message.predicted_actions.length > 0
                      ? message.predicted_actions
                          .map(formatLabel)
                          .join(", ")
                      : "None detected"}
                  </span>
                  <span data-label="Risk">
                    <Badge tone={message.risk_level ?? "neutral"}>
                      {message.risk_level
                        ? formatLabel(message.risk_level)
                        : "Not set"}
                    </Badge>
                  </span>
                  <span className={styles.status} data-label="Status">
                    {message.status ? formatLabel(message.status) : "Unknown"}
                  </span>
                  <span className={styles.time} data-label="Time">
                    {formatTime(message.created_at)}
                  </span>
                </div>
              ))}

              {rows.length === 0 && (
                <div className={styles.empty}>
                  No messages at this risk level.
                </div>
              )}
            </div>
          </>
        )}
      </Card>
    </>
  );
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Could not load message history. Please try again.";
}

export default History;
