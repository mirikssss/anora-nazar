// Карточка: тонкая рамка вместо тени, скругление 20px.
import type { HTMLAttributes, ReactNode } from "react";

import styles from "./Card.module.css";

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  as?: "section" | "article" | "div";
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  flush?: boolean;
  children: ReactNode;
}

export function Card({
  as: Tag = "section",
  title,
  subtitle,
  actions,
  flush = false,
  className,
  children,
  ...rest
}: CardProps) {
  const hasHeader = title !== undefined || actions !== undefined;
  return (
    <Tag {...rest} className={[styles.card, flush ? styles.flush : "", className ?? ""].join(" ")}>
      {hasHeader ? (
        <header className={styles.header}>
          <div>
            {title !== undefined ? <h2 className={styles.title}>{title}</h2> : null}
            {subtitle !== undefined ? <p className={styles.subtitle}>{subtitle}</p> : null}
          </div>
          {actions !== undefined ? <div className={styles.actions}>{actions}</div> : null}
        </header>
      ) : null}
      {flush ? <div className={styles.flushBody}>{children}</div> : children}
    </Tag>
  );
}
