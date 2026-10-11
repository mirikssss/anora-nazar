// Значение с полосой длины value / max: сравнение строк таблицы на глаз. Цвет — серый: это не состояние.
import styles from "./ValueBar.module.css";

interface ValueBarProps {
  value: number | null;
  max: number;
  text: string;
  /** Выделить строку, против которой сравнивают (например, «+ граф»). */
  emphasis?: boolean;
}

export function ValueBar({ value, max, text, emphasis = false }: ValueBarProps) {
  const share = value === null || max <= 0 ? 0 : Math.min(1, Math.max(0, value / max));
  return (
    <span className={styles.wrap}>
      <span className={styles.track} aria-hidden>
        <span
          className={[styles.fill, emphasis ? styles.emphasis : ""].join(" ")}
          style={{ transform: `scaleX(${String(share)})` }}
        />
      </span>
      <span className={styles.text}>{text}</span>
    </span>
  );
}
