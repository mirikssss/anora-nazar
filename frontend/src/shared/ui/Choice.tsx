// Выбор одного из немногих вариантов кнопками (сегменты) — вместо списка, когда вариантов 2–4.
import { useId } from "react";

import styles from "./Choice.module.css";

export interface ChoiceOption<V extends string> {
  value: V;
  label: string;
}

interface ChoiceProps<V extends string> {
  label: string;
  value: V | null;
  options: readonly ChoiceOption<V>[];
  onChange: (value: V) => void;
  error?: string | undefined;
}

export function Choice<V extends string>({ label, value, options, onChange, error }: ChoiceProps<V>) {
  const name = useId();
  return (
    <fieldset className={styles.choice} aria-invalid={error !== undefined || undefined}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.options}>
        {options.map((option) => (
          <label key={option.value} className={styles.option}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => {
                onChange(option.value);
              }}
              className="visually-hidden"
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {error !== undefined ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
