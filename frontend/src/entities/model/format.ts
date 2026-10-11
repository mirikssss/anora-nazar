// Показ метрик качества: PR-AUC — дробью с 95 % интервалом, recall и precision — долей, мера Брайера —
// дробью; нет значения — прочерк.
import type { Metrics } from "./report";
import { ru } from "@/shared/i18n/ru";
import { formatDecimal, formatNumber, formatShare } from "@/shared/lib/format";

const SCORE_DIGITS = 3;
const BRIER_DIGITS = 4;

function orNone(value: number | null, format: (value: number) => string): string {
  return value === null ? ru.common.none : format(value);
}

export function formatScore(value: number | null): string {
  return orNone(value, (v) => formatDecimal(v, SCORE_DIGITS));
}

export function formatBrier(value: number | null): string {
  return orNone(value, (v) => formatDecimal(v, BRIER_DIGITS));
}

export function formatRate(value: number | null): string {
  return orNone(value, formatShare);
}

export function formatCount(value: number | null): string {
  return orNone(value, formatNumber);
}

/** «0,784 [0,633; 0,900]» — PR-AUC с 95 % интервалом бутстрепа. */
export function formatPrAuc(metrics: Metrics | null): string {
  const value = formatScore(metrics?.prAuc ?? null);
  const ci = metrics?.prAucCi ?? null;
  return ci === null ? value : `${value} [${formatScore(ci[0])}; ${formatScore(ci[1])}]`;
}
