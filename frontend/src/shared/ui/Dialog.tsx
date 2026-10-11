// Модальное окно на нативном <dialog>: фокус и Esc — от браузера.
import { useEffect, useId, useRef, type ReactNode } from "react";

import { IconClose } from "@/shared/icons";

import styles from "./Dialog.module.css";

interface DialogProps {
  open: boolean;
  title: string;
  closeLabel: string;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
}

export function Dialog({ open, title, closeLabel, onClose, footer, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={ref} className={styles.dialog} aria-labelledby={titleId} onClose={onClose}>
      <header className={styles.header}>
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <button type="button" className={styles.close} aria-label={closeLabel} onClick={onClose}>
          <IconClose size={18} aria-hidden />
        </button>
      </header>
      <div className={styles.body}>{children}</div>
      {footer !== undefined ? <footer className={styles.footer}>{footer}</footer> : null}
    </dialog>
  );
}
