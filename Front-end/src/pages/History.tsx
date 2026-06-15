/* ============================================================
   Aegis · History page
   ------------------------------------------------------------
   A log of past governed messages: the incoming text, who sent
   it, the detected intent, the risk level and what the governance
   layer decided. Built as a CSS-grid "table" (rather than a real
   <table>) so it reflows cleanly on small screens. A filter lets
   the user narrow the list by risk tier.
   ============================================================ */

import { useMemo, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { Badge, riskTone } from "../components/Badge";
import { decisionLogs } from "../data/governance";
import type { RiskLevel } from "../types";
import styles from "./History.module.css";

type Filter = "All" | RiskLevel;
const filters: Filter[] = ["All", "Low", "Medium", "High"];

function History() {
  const [filter, setFilter] = useState<Filter>("All");

  const rows = useMemo(
    () =>
      filter === "All"
        ? decisionLogs
        : decisionLogs.filter((log) => log.risk === filter),
    [filter]
  );

  return (
    <>
      <PageHeader
        title="History"
        subtitle="A record of recent messages, the intent the assistant detected, and the decision it took."
        action={
          <div className={styles.filters}>
            {filters.map((f) => (
              <button
                key={f}
                className={`${styles.filter} ${filter === f ? styles.activeFilter : ""}`}
                onClick={() => setFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
        }
      />

      <Card>
        <div className={styles.table}>
          <div className={`${styles.row} ${styles.head}`}>
            <span>Message</span>
            <span>Contact</span>
            <span>Intent</span>
            <span>Risk</span>
            <span>Decision</span>
            <span>Time</span>
          </div>

          {rows.map((log) => (
            <div key={log.id} className={styles.row}>
              <span className={styles.message} data-label="Message">
                {log.message}
              </span>
              <span data-label="Contact">{log.contact}</span>
              <span data-label="Intent">{log.intent}</span>
              <span data-label="Risk">
                <Badge tone={riskTone(log.risk)}>{log.risk}</Badge>
              </span>
              <span className={styles.decision} data-label="Decision">
                {log.decision}
              </span>
              <span className={styles.time} data-label="Time">
                {log.time}
              </span>
            </div>
          ))}

          {rows.length === 0 && (
            <div className={styles.empty}>No messages at this risk level.</div>
          )}
        </div>
      </Card>
    </>
  );
}

export default History;
