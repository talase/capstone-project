/* ============================================================
   Aegis - Governance page
   ------------------------------------------------------------
   Lets the user configure how every assistant action is handled.
   Actions are grouped by risk tier (Low / Medium / High). Each
   action now offers all three modes - Automatic, Approval
   Required, Locked - so the user is in full control across every
   tier, not just the medium one.

   Each action has a survey-recommended `defaultMode` (from
   data/governance.ts). That option is labelled "(default)" in the
   dropdown, and a "Changed" tag appears when the user picks
   something other than the default. Choices are saved to
   localStorage and "Reset to default" restores every survey value.
   ============================================================ */

import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { Badge, riskTone } from "../components/Badge";
import { governanceActions } from "../data/governance";
import type { AutomationMode, GovernanceAction, RiskLevel } from "../types";
import styles from "./Governance.module.css";

const STORAGE_KEY = "aegis-governance";
const riskOrder: RiskLevel[] = ["Low", "Medium", "High"];
// Every action can be set to any of these three modes.
const allModes: AutomationMode[] = ["Automatic", "Approval Required", "Locked"];

/** Load saved mode choices and layer them on top of the canonical list. */
function loadActions(): GovernanceAction[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return governanceActions;

    const saved = JSON.parse(raw) as Partial<GovernanceAction>[];
    const savedModeById = new Map(saved.map((a) => [a.id, a.mode]));

    return governanceActions.map((action) => {
      const savedMode = savedModeById.get(action.id);
      // Restore a saved choice only if it is a valid mode; otherwise keep
      // the canonical default. defaultMode always comes from the code.
      return savedMode && allModes.includes(savedMode)
        ? { ...action, mode: savedMode }
        : action;
    });
  } catch {
    return governanceActions;
  }
}

function Governance() {
  const [actions, setActions] = useState<GovernanceAction[]>(loadActions);

  // Persist on every change.
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(actions));
  }, [actions]);

  function updateMode(id: number, mode: AutomationMode) {
    setActions((current) =>
      current.map((a) => (a.id === id ? { ...a, mode } : a))
    );
  }

  function reset() {
    setActions(governanceActions);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <>
      <PageHeader
        title="Governance"
        subtitle="Choose how the assistant handles each action."
        action={
          <button className={styles.reset} onClick={reset}>
            Reset to default
          </button>
        }
      />

      <div className={styles.groups}>
        {riskOrder.map((risk) => {
          const group = actions.filter((a) => a.risk === risk);
          return (
            <Card key={risk} title={`${risk} risk`} subtitle={`${group.length} actions`}>
              <div className={styles.list}>
                {group.map((action) => (
                  <div key={action.id} className={styles.row}>
                    <div className={styles.info}>
                      <div className={styles.name}>
                        <span>{action.action}</span>
                        <Badge tone={riskTone(action.risk)}>{action.risk}</Badge>
                        {action.mode !== action.defaultMode && (
                          <span className={styles.changed}>Changed</span>
                        )}
                      </div>
                      <p className={styles.desc}>{action.description}</p>
                    </div>

                    <select
                      className={styles.select}
                      value={action.mode}
                      onChange={(e) =>
                        updateMode(action.id, e.target.value as AutomationMode)
                      }
                    >
                      {allModes.map((m) => (
                        <option key={m} value={m}>
                          {m}
                          {m === action.defaultMode ? "  (default)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}

export default Governance;
