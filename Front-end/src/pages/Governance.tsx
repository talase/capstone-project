import { useCallback, useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { LockIcon } from "../components/icons";
import {
  ApiError,
  getActionSettings,
  updateActionSetting,
} from "../services/api";
import type { ActionRiskLevel, ActionSetting } from "../types";
import styles from "./Governance.module.css";

const riskLevels: ActionRiskLevel[] = ["low", "medium", "high"];

const riskDetails: Record<
  ActionRiskLevel,
  { title: string; behavior: string }
> = {
  low: {
    title: "Low risk",
    behavior:
      "The assistant may perform this action automatically when any contact requests it.",
  },
  medium: {
    title: "Medium risk",
    behavior:
      "The assistant pauses the action and asks for your approval through the n8n workflow.",
  },
  high: {
    title: "High risk",
    behavior:
      "The assistant informs you about the request, but it never performs the action.",
  },
};

function Governance() {
  const [settings, setSettings] = useState<ActionSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshSettings = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      setSettings(await getActionSettings());
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getActionSettings()
      .then((items) => {
        if (active) setSettings(items);
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

  async function changeRisk(
    setting: ActionSetting,
    riskLevel: ActionRiskLevel
  ) {
    if (!setting.is_editable || setting.risk_level === riskLevel) return;

    setSavingId(setting.id);
    setError(null);
    try {
      const updated = await updateActionSetting(setting.id, riskLevel);
      setSettings((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Governance"
        subtitle="Control whether each assistant action runs automatically, requires your approval, or is completely blocked."
        action={
          <button
            className={styles.refresh}
            onClick={() => void refreshSettings()}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        }
      />

      <div className={styles.riskGuide}>
        {riskLevels.map((risk) => (
          <div key={risk} className={`${styles.guideItem} ${styles[risk]}`}>
            <Badge tone={risk}>{riskDetails[risk].title}</Badge>
            <p>{riskDetails[risk].behavior}</p>
          </div>
        ))}
      </div>

      <Card
        title="Action settings"
        subtitle="Changes are saved directly to the action_settings table."
      >
        {loading ? (
          <p className={styles.muted}>Loading action settings...</p>
        ) : error && settings.length === 0 ? (
          <p className={styles.error}>{error}</p>
        ) : settings.length === 0 ? (
          <p className={styles.muted}>
            No action settings were found for this user.
          </p>
        ) : (
          <>
            {error && <p className={styles.error}>{error}</p>}
            <div className={styles.list}>
              {settings.map((setting) => (
                <div key={setting.id} className={styles.row}>
                  <div className={styles.info}>
                    <div className={styles.name}>
                      <span>{formatActionType(setting.action_type)}</span>
                      {!setting.is_editable && (
                        <span className={styles.fixed}>
                          <LockIcon size={12} />
                          Fixed by system
                        </span>
                      )}
                    </div>
                    <p className={styles.actionType}>{setting.action_type}</p>
                    {setting.description && (
                      <p className={styles.desc}>{setting.description}</p>
                    )}
                    <p className={styles.currentBehavior}>
                      {riskDetails[setting.risk_level].behavior}
                    </p>
                  </div>

                  <div className={styles.control}>
                    <Badge tone={setting.risk_level}>
                      {riskDetails[setting.risk_level].title}
                    </Badge>
                    <select
                      className={styles.select}
                      value={setting.risk_level}
                      disabled={
                        !setting.is_editable || savingId === setting.id
                      }
                      aria-label={`Risk level for ${formatActionType(
                        setting.action_type
                      )}`}
                      onChange={(event) =>
                        void changeRisk(
                          setting,
                          event.target.value as ActionRiskLevel
                        )
                      }
                    >
                      {riskLevels.map((risk) => (
                        <option key={risk} value={risk}>
                          {riskDetails[risk].title}
                        </option>
                      ))}
                    </select>
                    {savingId === setting.id && (
                      <span className={styles.saving}>Saving...</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </>
  );
}

function formatActionType(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Could not load the action settings. Please try again.";
}

export default Governance;
