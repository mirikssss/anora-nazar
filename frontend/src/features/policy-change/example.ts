// Примеры для формы предложения порога (правило «Интерфейс» п. 11): новое значение рядом с действующим,
// обоснование — из справочника подсказок демо. Каждый раз новые.
import { formatThreshold } from "@/entities/policy";
import { DEMO, pick } from "@/shared/demo";

const SIGNIFICANT_DIGITS = 2;

export function exampleValue(current: number): string {
  const [low, high] = DEMO.policyChangeShare;
  const sign = pick([-1, 1] as const);
  const shifted = current * (1 + sign * (low + Math.random() * (high - low)));
  const rounded = Number(shifted.toPrecision(SIGNIFICANT_DIGITS));
  if (!Number.isInteger(current)) return formatThreshold(rounded);
  // Целые пороги (число связей, актов) остаются целыми и не совпадают с действующим.
  const whole = Math.max(1, Math.round(rounded));
  return formatThreshold(whole === current ? current + 1 : whole);
}

export function exampleReason(): string {
  return pick(DEMO.policyReasons);
}
