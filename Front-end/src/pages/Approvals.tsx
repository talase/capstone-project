/* ============================================================
   Aegis - Approvals page
   ------------------------------------------------------------
   The human-in-the-loop queue: actions the assistant has
   detected but is NOT allowed to run on its own. Items are split
   into two groups by risk:

     - High risk  -> "Locked" actions (money, contracts, sensitive
                     files...). They can never be automated, so they
                     ALWAYS pass through here. BOTH Approve and Reject
                     open a confirmation pop-up (Modal): approving
                     also lets the user review/edit the exact response
                     before the final Confirm.
     - Medium risk -> "Approval Required" actions. A single click
                     approves or rejects them.

   State is local: `queue` holds the still-pending items, `resolved`
   counts this session's outcomes, and `dialog`/`draft` track the
   high-risk item currently being confirmed (and its editable
   response). In a later phase these become backend calls, but the
   page logic stays the same.
   ============================================================ */

import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Badge, riskTone } from "../components/Badge";
import { Modal } from "../components/Modal";
import { CheckIcon, XIcon, InboxIcon, LockIcon } from "../components/icons";
import { pendingApprovals } from "../data/governance";
import type { PendingAction } from "../types";
import styles from "./Approvals.module.css";

type DialogState = { item: PendingAction; kind: "approve" | "reject" };

function Approvals() {
  const [queue, setQueue] = useState<PendingAction[]>(pendingApprovals);
  const [resolved, setResolved] = useState({ approved: 0, rejected: 0 });

  // The high-risk item being confirmed in the pop-up (or null), plus the
  // editable response used when approving.
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [draft, setDraft] = useState("");

  /** Remove an item from the queue and record how it was resolved. */
  function resolve(id: number, outcome: "approved" | "rejected") {
    setQueue((current) => current.filter((item) => item.id !== id));
    setResolved((current) => ({ ...current, [outcome]: current[outcome] + 1 }));
  }

  /** Open the confirm pop-up for a high-risk item. */
  function openDialog(item: PendingAction, kind: "approve" | "reject") {
    setDialog({ item, kind });
    if (kind === "approve") setDraft(item.proposed);
  }

  function closeDialog() {
    setDialog(null);
  }

  function confirmDialog() {
    if (!dialog) return;
    resolve(dialog.item.id, dialog.kind === "approve" ? "approved" : "rejected");
    setDialog(null);
  }

  const highRisk = queue.filter((item) => item.risk === "High");
  const otherRisk = queue.filter((item) => item.risk !== "High");

  const counterLabel =
    highRisk.length > 0
      ? `${highRisk.length} high · ${otherRisk.length} medium`
      : `${queue.length} pending`;

  /** One queue card. High-risk cards get extra emphasis and a confirm gate. */
  function renderCard(item: PendingAction) {
    const isHigh = item.risk === "High";

    return (
      <article
        key={item.id}
        className={`${styles.card} ${isHigh ? styles.highCard : ""}`}
      >
        <header className={styles.cardHead}>
          <div className={styles.who}>
            <span className={styles.contact}>{item.contact}</span>
            <Badge tone={riskTone(item.risk)}>{item.risk}</Badge>
          </div>
          <span className={styles.time}>{item.time}</span>
        </header>

        {isHigh && (
          <p className={styles.lockNote}>
            <LockIcon size={13} />
            Locked action — can never be automated.
          </p>
        )}

        <p className={styles.message}>&ldquo;{item.message}&rdquo;</p>

        <p className={styles.intent}>
          Detected action: <span>{item.intent}</span>
        </p>

        <div className={`${styles.proposal} ${isHigh ? styles.proposalHigh : ""}`}>
          <span className={styles.proposalLabel}>Assistant proposes</span>
          <p>{item.proposed}</p>
        </div>

        <div className={styles.actions}>
          <button
            className={styles.reject}
            onClick={() =>
              isHigh ? openDialog(item, "reject") : resolve(item.id, "rejected")
            }
          >
            <XIcon size={16} />
            Reject
          </button>
          <button
            className={styles.approve}
            onClick={() =>
              isHigh ? openDialog(item, "approve") : resolve(item.id, "approved")
            }
          >
            <CheckIcon size={16} />
            Approve
          </button>
        </div>
      </article>
    );
  }

  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Actions the assistant has proposed and is holding until you decide."
        action={
          <span className={styles.counter}>
            <InboxIcon size={16} />
            {counterLabel}
          </span>
        }
      />

      {/* Session summary, only once something has been resolved. */}
      {resolved.approved + resolved.rejected > 0 && (
        <p className={styles.summary}>
          This session: <strong>{resolved.approved}</strong> approved,{" "}
          <strong>{resolved.rejected}</strong> rejected.
        </p>
      )}

      {queue.length === 0 ? (
        <div className={styles.empty}>
          <span className={styles.emptyMark}>
            <CheckIcon size={26} />
          </span>
          <p>All caught up</p>
          <span>No actions are waiting for your approval.</span>
        </div>
      ) : (
        <div className={styles.sections}>
          {highRisk.length > 0 && (
            <section>
              <header className={`${styles.sectionHead} ${styles.sectionHeadHigh}`}>
                <LockIcon size={15} />
                <h2 className={styles.sectionTitle}>
                  High risk · requires explicit approval
                </h2>
              </header>
              <div className={styles.list}>{highRisk.map(renderCard)}</div>
            </section>
          )}

          {otherRisk.length > 0 && (
            <section>
              <header className={styles.sectionHead}>
                <h2 className={styles.sectionTitle}>
                  Medium risk · awaiting approval
                </h2>
              </header>
              <div className={styles.list}>{otherRisk.map(renderCard)}</div>
            </section>
          )}
        </div>
      )}

      {/* Confirmation pop-up for high-risk approve / reject. */}
      {dialog && (
        <Modal
          title={
            dialog.kind === "approve"
              ? "Confirm high-risk approval"
              : "Confirm rejection"
          }
          onClose={closeDialog}
        >
          <p className={styles.dialogContext}>
            To <strong>{dialog.item.contact}</strong> · {dialog.item.intent}
          </p>

          {dialog.kind === "approve" ? (
            <>
              <label className={styles.confirmLabel} htmlFor="dialog-response">
                Response the assistant will send
              </label>
              <textarea
                id="dialog-response"
                className={styles.textarea}
                value={draft}
                rows={3}
                autoFocus
                onChange={(event) => setDraft(event.target.value)}
              />
              <p className={styles.confirmQuestion}>
                Are you sure you want to respond with this?
              </p>
              <div className={styles.actions}>
                <button className={styles.cancel} onClick={closeDialog}>
                  Cancel
                </button>
                <button
                  className={styles.approve}
                  disabled={!draft.trim()}
                  onClick={confirmDialog}
                >
                  <CheckIcon size={16} />
                  Confirm &amp; send
                </button>
              </div>
            </>
          ) : (
            <>
              <p className={styles.dialogText}>
                The assistant will not perform this action, and the proposed
                message won&rsquo;t be sent.
              </p>
              <p className={styles.confirmQuestion}>
                Are you sure you want to reject this?
              </p>
              <div className={styles.actions}>
                <button className={styles.cancel} autoFocus onClick={closeDialog}>
                  Cancel
                </button>
                <button className={styles.dangerSolid} onClick={confirmDialog}>
                  <XIcon size={16} />
                  Confirm reject
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}

export default Approvals;
