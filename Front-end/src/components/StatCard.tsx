/* ============================================================
   Aegis · StatCard
   ------------------------------------------------------------
   A compact metric tile for the Dashboard: an icon, a label and
   a big number. The `accent` prop tints the icon and the thin
   top strip so a row of stat cards can colour-code by risk.
   ============================================================ */

import type { ReactNode } from "react";
import styles from "./StatCard.module.css";

type Accent = "brand" | "low" | "medium" | "high";

interface StatCardProps {
  label: string;
  value: number | string;
  icon: ReactNode;
  accent?: Accent;
  hint?: string;
}

export function StatCard({
  label,
  value,
  icon,
  accent = "brand",
  hint,
}: StatCardProps) {
  return (
    <div className={`${styles.card} ${styles[accent]}`}>
      <div className={styles.top}>
        <span className={styles.icon}>{icon}</span>
        <span className={styles.label}>{label}</span>
      </div>
      <p className={styles.value}>{value}</p>
      {hint && <p className={styles.hint}>{hint}</p>}
    </div>
  );
}
