/* ============================================================
   Aegis · Dashboard page
   ------------------------------------------------------------
   The landing overview. It summarises the live state of the
   console: how many actions are pending approval, how many
   decisions have been logged, and how the governance policy is
   currently configured. It then previews the most recent decisions
   (mirroring the History page) and explains the three risk tiers.
   All counts are derived from the shared data with useMemo, so the
   overview stays in sync with the other pages.
   ============================================================ */

import { useMemo } from "react";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { BoltIcon, LockIcon, HistoryIcon, InboxIcon } from "../components/icons";
import {
  governanceActions,
  decisionLogs,
  pendingApprovals,
} from "../data/governance";
import styles from "./Dashboard.module.css";

function Dashboard() {
  // Live counts that mirror the other pages.
  const stats = useMemo(
    () => ({
      pending: pendingApprovals.length,
      decisions: decisionLogs.length,
      locked: governanceActions.filter((a) => a.mode === "Locked").length,
      automatic: governanceActions.filter((a) => a.mode === "Automatic").length,
    }),
    []
  );

  const riskTiers = [
    {
      tone: "low" as const,
      title: "Low risk",
      text: "Everyday chat and safe replies are handled automatically, with no interruption.",
    },
    {
      tone: "medium" as const,
      title: "Medium risk",
      text: "Meetings, forwarded messages and non-sensitive files are proposed and wait for your approval.",
    },
    {
      tone: "high" as const,
      title: "High risk",
      text: "Money, agreements, emergencies and sensitive files are locked — always blocked until you confirm.",
    },
  ];

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="An overview of how the assistant is handling incoming messages and the governance rules currently in effect."
      />

      <div className={styles.stats}>
        <StatCard
          label="Pending approvals"
          value={stats.pending}
          accent="medium"
          icon={<InboxIcon />}
          hint="Waiting for your decision"
        />
        <StatCard
          label="Decisions logged"
          value={stats.decisions}
          accent="brand"
          icon={<HistoryIcon />}
          hint="Recent governed messages"
        />
        <StatCard
          label="Locked actions"
          value={stats.locked}
          accent="high"
          icon={<LockIcon />}
          hint="Always blocked until confirmed"
        />
        <StatCard
          label="Automatic actions"
          value={stats.automatic}
          accent="low"
          icon={<BoltIcon />}
          hint="Run without approval"
        />
      </div>

      <div className={styles.panels}>
        <Card
          title="How governance works"
          subtitle="Every detected action is sorted into one of three risk tiers."
        >
          <div className={styles.tiers}>
            {riskTiers.map((tier) => (
              <div key={tier.title} className={styles.tier}>
                <Badge tone={tier.tone}>{tier.title}</Badge>
                <p>{tier.text}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

export default Dashboard;
