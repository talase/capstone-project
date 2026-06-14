/* ============================================================
   Aegis · PageHeader
   ------------------------------------------------------------
   The title + subtitle block shown at the top of every page.
   Centralising it keeps the heading size, spacing and the
   optional right-hand action area identical across all pages.
   ============================================================ */

import type { ReactNode } from "react";
import styles from "./PageHeader.module.css";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Optional controls shown on the right (e.g. a Reset button). */
  action?: ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <h1>{title}</h1>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
      {action && <div className={styles.action}>{action}</div>}
    </header>
  );
}
