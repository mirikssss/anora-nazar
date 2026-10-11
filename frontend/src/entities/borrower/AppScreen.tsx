// Экран мобильного приложения банка: крупный заголовок, одно главное действие внизу (Блок 5, п. 4).
import type { ReactNode } from "react";

import styles from "./AppScreen.module.css";

interface AppScreenProps {
  title: ReactNode;
  lead?: ReactNode;
  /** Над заголовком: возврат к списку или подпись раздела. */
  top?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

export function AppScreen({ title, lead, top, actions, children }: AppScreenProps) {
  return (
    <div className={styles.screen}>
      {top !== undefined ? <div className={styles.top}>{top}</div> : null}
      <h2 className={styles.title}>{title}</h2>
      {lead !== undefined ? <p className={styles.lead}>{lead}</p> : null}
      {children !== undefined ? <div className={styles.content}>{children}</div> : null}
      {actions !== undefined ? <div className={styles.actions}>{actions}</div> : null}
    </div>
  );
}
