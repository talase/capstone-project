/* ============================================================
   Aegis · Modal
   ------------------------------------------------------------
   A small accessible dialog rendered through a React portal onto
   <body>, so it always overlays the whole app regardless of where
   it is used. It dims the page behind it, closes on Escape or a
   backdrop click, and locks page scroll while open. The title and
   body are passed in by the caller; the action buttons live in the
   children so each caller controls its own confirm/cancel flow.
   ============================================================ */

import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import styles from "./Modal.module.css";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ title, onClose, children }: ModalProps) {
  // Close on Escape and prevent the page behind from scrolling.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return createPortal(
    // Clicking the backdrop cancels; clicks inside the dialog do not bubble.
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className={styles.title}>{title}</h2>
        {children}
      </div>
    </div>,
    document.body
  );
}
