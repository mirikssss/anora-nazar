// Бейдж состояния: полностью скруглённый. Цвет — только у состояний; категории — серые.
import type { ReactNode } from "react";

import styles from "./Badge.module.css";

export type BadgeTone = "neutral" | "outline" | "green" | "yellow" | "orange" | "red" | "blue";

interface BadgeProps {
  tone?: BadgeTone;
  /** Точка состояния перед словом — для плотных таблиц вместо заливки. */
  dot?: boolean;
  title?: string;
  children: ReactNode;
}

export function Badge({ tone = "neutral", dot = false, title, children }: BadgeProps) {
  return (
    <span className={[styles.badge, dot ? styles.dotted : styles[tone]].join(" ")} title={title}>
      {dot ? <span className={[styles.dot, styles[`dot-${tone}`]].join(" ")} aria-hidden /> : null}
      {children}
    </span>
  );
}
