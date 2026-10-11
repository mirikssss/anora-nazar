// Поле формы с подписью, подсказкой и ошибкой: ввод текста, числа или выбор из списка.
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

import { IconChevronDown } from "@/shared/icons";

import styles from "./Field.module.css";

interface FieldFrameProps {
  label: ReactNode;
  hint?: ReactNode | undefined;
  error?: string | undefined;
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

function FieldFrame({ label, hint, error, children }: FieldFrameProps) {
  const id = useId();
  const hintId = hint !== undefined ? `${id}-hint` : undefined;
  const errorId = error !== undefined ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      {children({ id, describedBy, invalid: error !== undefined })}
      {hint !== undefined ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      {error !== undefined ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: ReactNode;
  hint?: ReactNode | undefined;
  error?: string | undefined;
}

export function TextField({ label, hint, error, className, ...rest }: TextFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <input
          {...rest}
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={[styles.control, className ?? ""].join(" ")}
        />
      )}
    </FieldFrame>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: ReactNode;
  options: readonly SelectOption[];
  placeholder?: string;
  hint?: ReactNode | undefined;
  error?: string | undefined;
}

export function SelectField({ label, options, placeholder, hint, error, ...rest }: SelectFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <div className={styles.selectWrap}>
          <select
            {...rest}
            id={id}
            aria-describedby={describedBy}
            aria-invalid={invalid || undefined}
            className={[styles.control, styles.select].join(" ")}
          >
            {placeholder !== undefined ? (
              <option value="" disabled>
                {placeholder}
              </option>
            ) : null}
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <IconChevronDown size={16} className={styles.chevron} aria-hidden />
        </div>
      )}
    </FieldFrame>
  );
}
