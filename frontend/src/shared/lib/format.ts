// Форматирование сумм в сумах, дат, времени и долей. Пояс — банка, из конфигурации.
import { env } from "@/shared/config/env";
import { ru } from "@/shared/i18n/ru";

const LOCALE = "ru-RU";

const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat(LOCALE, { style: "percent", maximumFractionDigits: 1 });
const date = new Intl.DateTimeFormat(LOCALE, {
  timeZone: env.timeZone,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});
const time = new Intl.DateTimeFormat(LOCALE, {
  timeZone: env.timeZone,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const timeWithSeconds = new Intl.DateTimeFormat(LOCALE, {
  timeZone: env.timeZone,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** «30 000 000 сум» — с неразрывными пробелами; показывать с классом num (табличные цифры). */
export function formatSum(amount: number): string {
  return `${integer.format(amount)}\u00a0${ru.common.currency}`;
}

export function formatNumber(value: number): string {
  return integer.format(value);
}

export function formatShare(value: number): string {
  return percent.format(value);
}

/** Дробное число с заданным числом знаков: PR-AUC, мера Брайера. */
export function formatDecimal(value: number, digits: number): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** ДД.ММ.ГГГГ */
export function formatDate(iso: string): string {
  return date.format(new Date(iso));
}

/** ЧЧ:ММ, 24 часа */
export function formatTime(iso: string, withSeconds = false): string {
  return (withSeconds ? timeWithSeconds : time).format(new Date(iso));
}

/** ДД.ММ.ГГГГ ЧЧ:ММ */
export function formatDateTime(iso: string): string {
  return `${formatDate(iso)} ${formatTime(iso)}`;
}

/** Длинные хеши и ключи показываются началом: полное значение — в title. */
export function shortHash(value: string, length = 12): string {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

/** Значение из доказательств, признаков или журнала: строка как есть, объект — компактным JSON. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ru.common.none;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value) && value.length === 0) return ru.common.none;
  return JSON.stringify(value);
}

/** Целое из поля ввода: пробелы между разрядами допустимы; иначе null. */
export function parseInteger(value: string): number | null {
  const digits = value.replace(/\s/g, "");
  return /^\d+$/.test(digits) ? Number(digits) : null;
}
