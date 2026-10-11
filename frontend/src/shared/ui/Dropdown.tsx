// Выпадающее меню с группами: открывается кнопкой, стрелки двигают по пунктам, Esc закрывает.
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { IconCheck, IconChevronDown } from "@/shared/icons";

import styles from "./Dropdown.module.css";

export interface DropdownItem {
  key: string;
  label: string;
  description?: string;
  selected?: boolean;
  onSelect: () => void;
}

export interface DropdownGroup {
  key: string;
  title: string;
  items: readonly DropdownItem[];
}

interface DropdownProps {
  /** Подпись кнопки: что выбрано сейчас. */
  trigger: ReactNode;
  label: string;
  groups: readonly DropdownGroup[];
  align?: "start" | "end";
}

export function Dropdown({ trigger, label, groups, align = "end" }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    rootRef.current?.querySelector<HTMLElement>("[role=menuitemradio]")?.focus();
    return () => {
      document.removeEventListener("pointerdown", close);
    };
  }, [open]);

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(rootRef.current?.querySelectorAll<HTMLElement>("[role=menuitemradio]") ?? []);
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      setOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      items[(index + step + items.length) % items.length]?.focus();
    }
  };

  return (
    <div ref={rootRef} className={styles.root}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.trigger}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={label}
        onClick={() => {
          setOpen((value) => !value);
        }}
      >
        <span className={styles.triggerText}>{trigger}</span>
        <IconChevronDown size={16} aria-hidden />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          className={[styles.menu, styles[align]].join(" ")}
          onKeyDown={onMenuKeyDown}
        >
          {groups.map((group) => (
            <div key={group.key} role="group" aria-label={group.title} className={styles.group}>
              <p className={styles.groupTitle} aria-hidden>
                {group.title}
              </p>
              {group.items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  role="menuitemradio"
                  aria-checked={item.selected === true}
                  className={styles.item}
                  onClick={() => {
                    setOpen(false);
                    item.onSelect();
                  }}
                >
                  <span className={styles.itemText}>
                    <span>{item.label}</span>
                    {item.description !== undefined ? (
                      <span className={styles.itemDescription}>{item.description}</span>
                    ) : null}
                  </span>
                  {item.selected === true ? <IconCheck size={16} aria-hidden /> : null}
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
