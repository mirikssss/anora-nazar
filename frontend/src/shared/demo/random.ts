// Случайные значения для подсказок демо. Генератор на фронте — исключение из правила «демо-данные только
// с бэка» по прямому указанию владельца (11.10.2026): подсказки по Tab, каждый раз разные.
export function intBetween(min: number, max: number): number {
  return min + Math.floor(Math.random() * (max - min + 1));
}

export function pick<T>(items: readonly T[]): T {
  const item = items[intBetween(0, items.length - 1)];
  if (item === undefined) throw new Error("Пустой список для выбора");
  return item;
}

export function digits(count: number): string {
  return Array.from({ length: count }, () => String(intBetween(0, 9))).join("");
}

export function hex(count: number): string {
  return Array.from({ length: count }, () => intBetween(0, 15).toString(16)).join("");
}

/** Целое в диапазоне с шагом: суммы кредита кратны шагу, как в реальных заявках. */
export function stepBetween(min: number, max: number, step: number): number {
  return intBetween(Math.ceil(min / step), Math.floor(max / step)) * step;
}

/** Множитель с логнормальным разбросом вокруг 1: цена товара вокруг рыночной медианы. */
export function logNormalFactor(sigma: number): number {
  const gaussian = Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
  return Math.exp(sigma * gaussian);
}
