// Заглушка загрузки: серые строки вместо спиннера (Блок 5, п. 8).
import styles from "./Skeleton.module.css";

interface SkeletonProps {
  rows?: number;
  /** Подпись для экранного диктора. */
  label: string;
}

export function Skeleton({ rows = 3, label }: SkeletonProps) {
  return (
    <div className={styles.skeleton} role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className={styles.row} />
      ))}
    </div>
  );
}
