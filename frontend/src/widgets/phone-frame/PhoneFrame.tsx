// Рамка телефона для приложения заёмщика на широком экране; на телефоне рамки нет — приложение на весь экран.
import type { ReactNode } from "react";

import styles from "./PhoneFrame.module.css";

export function PhoneFrame({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className={styles.frame} aria-label={label}>
      <div className={styles.screen}>{children}</div>
    </section>
  );
}
