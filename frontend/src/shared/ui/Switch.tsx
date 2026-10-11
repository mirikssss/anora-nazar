// Переключатель вкл/выкл с подписью и пояснением.
import { useId, type ReactNode } from "react";

import styles from "./Switch.module.css";

interface SwitchProps {
  label: ReactNode;
  description?: ReactNode;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

export function Switch({ label, description, checked, disabled = false, onChange }: SwitchProps) {
  const id = useId();
  return (
    <div className={styles.row}>
      <div className={styles.text}>
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
        {description !== undefined ? <p className={styles.description}>{description}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        className={styles.track}
        onClick={() => {
          onChange(!checked);
        }}
      >
        <span className={styles.thumb} />
      </button>
    </div>
  );
}
