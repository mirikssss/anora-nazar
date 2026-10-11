// Заголовок страницы: название, пояснение одной строкой, метка («симулятор») и действия.
import type { ReactNode } from "react";

import styles from "./PageHeader.module.css";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  tag?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, tag, actions }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.text}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {tag}
        </div>
        {subtitle !== undefined ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {actions !== undefined ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}
