// Подписи и значения порогов политики. Подпись — из словаря по пути; нет подписи — сам путь.
import { label, ru } from "@/shared/i18n/ru";
import { formatDecimal, formatNumber } from "@/shared/lib/format";

const MAX_DIGITS = 6;

export function thresholdTitle(path: string): string {
  return label(ru.risk.policy.thresholdTitles, path);
}

/** Значение как задано в политике: «3 000 000», «0,25» — без добавленных нулей; переключатель — «включено». */
export function formatThreshold(value: number | boolean): string {
  if (typeof value === "boolean") return value ? ru.risk.policy.on : ru.risk.policy.off;
  if (Number.isInteger(value)) return formatNumber(value);
  const digits = Math.min(MAX_DIGITS, String(value).split(".")[1]?.length ?? MAX_DIGITS);
  return formatDecimal(value, digits);
}

/** Число из поля ввода: десятичная запятая и пробелы между разрядами допустимы; иначе null. */
export function parseThreshold(input: string): number | null {
  const normalized = input.replace(/\s/g, "").replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return null;
  return Number(normalized);
}
