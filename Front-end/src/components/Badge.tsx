/* ============================================================
   Aegis · Badge
   ------------------------------------------------------------
   Small coloured pill used to show a risk level (Low / Medium /
   High) or a generic status. The `tone` prop picks the colour
   set; a leading dot is drawn purely with CSS. Reused on the
   Dashboard, Approvals, Governance and History pages so the visual
   language for risk stays identical everywhere.
   ============================================================ */

import type { ReactNode } from "react";
import styles from "./Badge.module.css";
import type { RiskLevel } from "../types";

type Tone = "low" | "medium" | "high" | "neutral";

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
}

export function Badge({ children, tone = "neutral", dot = true }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      {dot && <span className={styles.dot} />}
      {children}
    </span>
  );
}

/** Helper: map a RiskLevel ("Low"/"Medium"/"High") to a badge tone. */
export function riskTone(risk: RiskLevel): Tone {
  if (risk === "Low") return "low";
  if (risk === "Medium") return "medium";
  return "high";
}
