/* ============================================================
   Aegis · Card
   ------------------------------------------------------------
   The basic surface container used throughout the app — a panel
   with a background, border, rounded corners and soft shadow.
   An optional title/subtitle header keeps section headings
   consistent. Anything can be placed inside via children.
   ============================================================ */

import type { ReactNode } from "react";
import styles from "./Card.module.css";

interface CardProps {
  title?: string;
  subtitle?: string;
  /** Optional element rendered on the right of the header (e.g. a button). */
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, subtitle, action, children, className }: CardProps) {
  return (
    <section className={`${styles.card} ${className ?? ""}`}>
      {(title || action) && (
        <header className={styles.header}>
          <div>
            {title && <h2 className={styles.title}>{title}</h2>}
            {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
