// Пустое состояние и ошибка загрузки: что случилось и что делать дальше.
import type { ReactNode } from "react";

import { IconAlert, type Icon } from "@/shared/icons";

import styles from "./StateMessage.module.css";

interface StateMessageProps {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "error";
  icon?: Icon;
}

export function StateMessage({ title, description, action, tone = "neutral", icon }: StateMessageProps) {
  const IconComponent = icon ?? (tone === "error" ? IconAlert : undefined);
  return (
    <div className={[styles.state, styles[tone]].join(" ")} role={tone === "error" ? "alert" : undefined}>
      {IconComponent ? <IconComponent size={20} className={styles.icon} aria-hidden /> : null}
      <p className={styles.title}>{title}</p>
      {description !== undefined ? <p className={styles.description}>{description}</p> : null}
      {action !== undefined ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
