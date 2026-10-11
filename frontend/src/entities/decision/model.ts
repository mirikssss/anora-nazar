// Решение узла: типы из OpenAPI и разбор неизменяемой записи решения.
import type { NodeSchemas } from "@/shared/api";

export type Decision = NodeSchemas["schemas"]["DecisionOut"];
export type Reason = NodeSchemas["schemas"]["Reason"];
export type DecisionRecord = NodeSchemas["schemas"]["DecisionRecordOut"];
export type Replay = NodeSchemas["schemas"]["ReplayOut"];
export type Comparison = NodeSchemas["schemas"]["ComparisonOut"];
export type Level = NonNullable<Reason["level"]>;

const LEVELS: readonly string[] = ["green", "yellow", "red"] satisfies Level[];

export function asLevel(value: string | null | undefined): Level | null {
  return value != null && LEVELS.includes(value) ? (value as Level) : null;
}

/** Причины состояния источников и моделей (SYSTEM_*) не говорят о риске — их показываем отдельно. */
export function splitReasons(reasons: readonly Reason[]): { risk: Reason[]; system: Reason[] } {
  const system = reasons.filter((reason) => reason.code.startsWith("SYSTEM_"));
  return { risk: reasons.filter((reason) => !system.includes(reason)), system };
}

// Запись решения на бэке — JSONB без схемы в OpenAPI (просьба типизировать отправлена бэку).
// До этого читаем только нужные поля с проверкой формы; чего нет — не показываем.
type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export interface DecisionResult {
  level: Level | null;
  action: string | null;
  outcome: string | null;
  validUntil: string | null;
  reasons: Reason[];
}

export interface DecisionVersions {
  policy: string | null;
  reasons: string | null;
  featureSet: string | null;
  models: string[];
  shadowModels: string[];
}

export interface ParsedRecord {
  result: DecisionResult;
  versions: DecisionVersions;
  features: Json | null;
}

function isReason(value: unknown): value is Reason {
  return isObject(value) && typeof value.code === "string" && typeof value.source === "string";
}

export function parseResult(value: unknown): DecisionResult {
  const result = isObject(value) ? value : {};
  return {
    level: asLevel(text(result.level)),
    action: text(result.action),
    outcome: text(result.outcome),
    validUntil: text(result.valid_until),
    reasons: Array.isArray(result.reasons) ? result.reasons.filter(isReason) : [],
  };
}

function modelLabel(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (isObject(value)) return text(value.name) ?? text(value.model_version_id) ?? JSON.stringify(value);
  return null;
}

export function parseRecord(record: DecisionRecord["record"]): ParsedRecord {
  const versions = isObject(record.versions) ? record.versions : {};
  const inputs = isObject(record.inputs) ? record.inputs : {};
  const features =
    isObject(inputs.features) && isObject(inputs.features.values) ? inputs.features.values : null;
  const models = Array.isArray(versions.models) ? versions.models : [];
  const shadow = Array.isArray(versions.shadow_models) ? versions.shadow_models : [];
  return {
    result: parseResult(record.result),
    versions: {
      policy: text(versions.policy),
      reasons: text(versions.reasons),
      featureSet: text(versions.feature_set),
      models: models.map(modelLabel).filter((item): item is string => item !== null),
      shadowModels: shadow.map(modelLabel).filter((item): item is string => item !== null),
    },
    features,
  };
}
