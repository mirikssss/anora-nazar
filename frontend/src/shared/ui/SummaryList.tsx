// Сводка «подпись — значение» (GOV.UK Summary list): условия заявки, версии решения.
import type { ReactNode } from "react";

import styles from "./SummaryList.module.css";

export interface SummaryRow {
  key: string;
  label: ReactNode;
  value: ReactNode;
}

export function SummaryList({ rows }: { rows: readonly SummaryRow[] }) {
  return (
    <dl className={styles.list}>
      {rows.map((row) => (
        <div key={row.key} className={styles.row}>
          <dt className={styles.label}>{row.label}</dt>
          <dd className={styles.value}>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
