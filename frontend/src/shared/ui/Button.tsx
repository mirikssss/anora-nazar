// Кнопка: основная (акцент банка), вторичная (серая подложка), текстовая, тревожная (красная рамка).
import type { ButtonHTMLAttributes } from "react";

import type { Icon } from "@/shared/icons";

import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "alarm";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  icon?: Icon;
  /** Действие идёт: кнопка заблокирована, подпись не меняется — без спиннера. */
  pending?: boolean;
  wide?: boolean;
  /** На телефоне остаётся только значок; подпись уходит в aria-label. */
  iconOnlyOnPhone?: boolean;
  children: string;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon: IconComponent,
  pending = false,
  wide = false,
  iconOnlyOnPhone = false,
  disabled,
  className,
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const classes = [
    styles.button,
    styles[variant],
    styles[size],
    wide ? styles.wide : "",
    iconOnlyOnPhone ? styles.iconOnlyOnPhone : "",
    className ?? "",
  ];
  return (
    <button
      {...rest}
      type={type}
      className={classes.join(" ")}
      disabled={disabled === true || pending}
      aria-busy={pending || undefined}
      aria-label={iconOnlyOnPhone ? children : rest["aria-label"]}
    >
      {IconComponent ? <IconComponent size={16} aria-hidden /> : null}
      <span>{children}</span>
    </button>
  );
}
