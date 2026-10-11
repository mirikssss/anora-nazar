// Чтение JSON без схемы в OpenAPI: только нужные поля с проверкой типа; чего нет — null.
export type Json = Record<string, unknown>;

export function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function obj(value: unknown): Json | null {
  return isObject(value) ? value : null;
}

export function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function strings(value: unknown): string[] {
  return list(value).filter((item): item is string => typeof item === "string");
}

/** Объект «ключ → число», например доли по группам. */
export function numberMap(value: unknown): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [key, item] of Object.entries(obj(value) ?? {})) {
    const parsed = num(item);
    if (parsed !== null) result[key] = parsed;
  }
  return result;
}
