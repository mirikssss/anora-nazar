// Решение узла: типы из OpenAPI и разбор неизменяемой записи решения.
import type { NodeSchemas } from "@/shared/api";
import { isObject, list, num, obj, str as text, type Json } from "@/shared/lib/json";

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
  const result = obj(value) ?? {};
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
  const versions = obj(record.versions) ?? {};
  const inputs = obj(record.inputs) ?? {};
  const features = obj(obj(inputs.features)?.values);
  const models = list(versions.models);
  const shadow = list(versions.shadow_models);
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

export interface Contribution {
  feature: string;
  value: unknown;
  contribution: number;
  reasonCode: string | null;
}

export interface ModelEvidence {
  modelVersionId: string | null;
  probability: number | null;
  riskCost: number | null;
  riskCostIsEstimate: boolean;
  contributions: Contribution[];
}

/** Доказательство причины MODEL_*: балл, оценочная стоимость риска и вклад признаков (у других причин — null). */
export function modelEvidence(reason: Reason): ModelEvidence | null {
  const item = reason.code.startsWith("MODEL_") ? obj(reason.evidence[0]) : null;
  if (item === null) return null;
  return {
    modelVersionId: text(item.model_version_id),
    probability: num(item.probability),
    riskCost: num(item.risk_cost_estimate),
    riskCostIsEstimate: item.risk_cost_is_estimate === true,
    contributions: list(item.contributions).flatMap((raw) => {
      const entry = obj(raw);
      const feature = text(entry?.feature);
      const contribution = num(entry?.contribution);
      return entry !== null && feature !== null && contribution !== null
        ? [{ feature, value: entry.value, contribution, reasonCode: text(entry.reason_code) }]
        : [];
    }),
  };
}
