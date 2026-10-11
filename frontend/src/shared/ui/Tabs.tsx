// Вкладки: стрелки влево и вправо переключают, как у WAI-ARIA tabs; содержимое рисует вызывающий.
import { useRef, type KeyboardEvent } from "react";

import styles from "./Tabs.module.css";

export interface TabItem {
  key: string;
  label: string;
}

interface TabsProps {
  label: string;
  items: readonly TabItem[];
  selected: string;
  onSelect: (key: string) => void;
  /** id панели, которую подписывают вкладки. */
  panelId: string;
}

export function Tabs({ label, items, selected, onSelect, panelId }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const index = items.findIndex((item) => item.key === selected);
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = items[(index + step + items.length) % items.length];
    if (next === undefined) return;
    onSelect(next.key);
    listRef.current?.querySelector<HTMLElement>(`[data-key="${next.key}"]`)?.focus();
  };
  return (
    <div ref={listRef} role="tablist" aria-label={label} className={styles.tabs} onKeyDown={onKeyDown}>
      {items.map((item) => {
        const active = item.key === selected;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            data-key={item.key}
            aria-selected={active}
            aria-controls={panelId}
            tabIndex={active ? 0 : -1}
            className={[styles.tab, active ? styles.active : ""].join(" ")}
            onClick={() => {
              onSelect(item.key);
            }}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
