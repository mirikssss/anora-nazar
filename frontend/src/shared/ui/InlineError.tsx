// Ошибка действия рядом с кнопкой: что не получилось, словами бэка.
import { IconAlert } from "@/shared/icons";

import styles from "./InlineError.module.css";

export function InlineError({ message }: { message: string }) {
  return (
    <p className={styles.error} role="alert">
      <IconAlert size={16} aria-hidden className={styles.icon} />
      <span>{message}</span>
    </p>
  );
}
