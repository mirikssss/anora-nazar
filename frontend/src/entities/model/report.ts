// Отчёт качества: скользящая проверка по времени, кандидаты, абляция, строгая изоляция групп,
// справедливость, нагрузка и проверка point-in-time. В OpenAPI отчёт — JSON без схемы; читаем нужные поля
// с проверкой, чего нет — null.
import { list, num, numberMap, obj, str, strings, type Json } from "@/shared/lib/json";

/** Точка при доле ручной проверки: ключ доли — как пришёл с бэка («1%», «2%»). */
export interface ReviewPoint {
  share: string;
  reviewed: number | null;
  recall: number | null;
  precision: number | null;
  falseReviewShare: number | null;
}

export interface Metrics {
  applications: number | null;
  positives: number | null;
  positiveRate: number | null;
  prAuc: number | null;
  prAucCi: readonly [number, number] | null;
  randomPrAuc: number | null;
  brier: number | null;
  recallAtFpr: number | null;
  review: ReviewPoint[];
}

export interface Fold {
  testFrom: string | null;
  train: number | null;
  positivesTrain: number | null;
  test: number | null;
  positivesTest: number | null;
  excludedFromTraining: number | null;
  heldOutSuppliers: number | null;
}

export interface FairnessGroup {
  key: string;
  falsePositiveRate: Record<string, number>;
  maxGap: number | null;
}

/** Вариант абляции или проверки: либо метрики, либо код статуса (сеть не подключена, мало меток). */
export interface Variant {
  key: string;
  metrics: Metrics | null;
  status: string | null;
}

export interface ModelReport {
  model: string;
  typology: string | null;
  points: string[];
  modelVersionId: string | null;
  skipped: string | null;
  family: string | null;
  final: { train: number | null; positives: number | null; rounds: number | null };
  folds: Fold[];
  candidates: Variant[];
  test: Metrics | null;
  byChannel: Record<string, Metrics>;
  separateByChannel: Record<string, Metrics>;
  ablation: Variant[];
  strict: { status: string | null; test: Metrics | null; positivesTrainByFold: number[] };
  fairness: { threshold: number | null; groups: FairnessGroup[] };
  load: {
    days: number | null;
    worstDay: string | null;
    worstDayFlagged: number | null;
    worstDayApplications: number | null;
    meanPerDay: number | null;
    p95PerDay: number | null;
  };
}

export interface PointInTime {
  checked: number | null;
  mismatched: number | null;
  byFeature: Record<string, number>;
}

export interface QualityReport {
  config: string | null;
  featureSet: string | null;
  cutoff: string | null;
  examples: number | null;
  f2Mode: string | null;
  pointInTime: PointInTime | null;
  models: ModelReport[];
}

function interval(value: unknown): readonly [number, number] | null {
  const [low, high] = list(value).map(num);
  return low !== undefined && high !== undefined && low !== null && high !== null ? [low, high] : null;
}

function review(value: unknown): ReviewPoint[] {
  return Object.entries(obj(value) ?? {}).flatMap(([share, item]) => {
    const point = obj(item);
    return point === null
      ? []
      : [
          {
            share,
            reviewed: num(point.reviewed),
            recall: num(point.recall),
            precision: num(point.precision),
            falseReviewShare: num(point.false_review_share),
          },
        ];
  });
}

function metrics(value: unknown): Metrics | null {
  const m = obj(value);
  if (m === null || !("pr_auc" in m || "applications" in m)) return null;
  return {
    applications: num(m.applications),
    positives: num(m.positives),
    positiveRate: num(m.positive_rate),
    prAuc: num(m.pr_auc),
    prAucCi: interval(m.pr_auc_ci95),
    randomPrAuc: num(m.random_pr_auc),
    brier: num(m.brier),
    recallAtFpr: num(m.recall_at_fpr),
    review: review(m.review),
  };
}

function metricsMap(value: unknown): Record<string, Metrics> {
  const result: Record<string, Metrics> = {};
  for (const [key, item] of Object.entries(obj(value) ?? {})) {
    const parsed = metrics(item);
    if (parsed !== null) result[key] = parsed;
  }
  return result;
}

function variants(value: unknown): Variant[] {
  return Object.entries(obj(value) ?? {}).map(([key, item]) => ({
    key,
    metrics: metrics(item),
    status: str(obj(item)?.status),
  }));
}

function fold(value: unknown): Fold | null {
  const f = obj(value);
  if (f === null) return null;
  return {
    testFrom: str(f.test_from),
    train: num(f.train),
    positivesTrain: num(f.positives_train),
    test: num(f.test),
    positivesTest: num(f.positives_test),
    excludedFromTraining: num(f.excluded_from_training),
    heldOutSuppliers: num(f.held_out_suppliers),
  };
}

const FAIRNESS_GROUPS = ["gender", "age_band"] as const;

function modelReport(raw: Json): ModelReport {
  const final = obj(raw.final) ?? {};
  const strict = obj(raw.strict_all_groups) ?? {};
  const fairness = obj(raw.fairness) ?? {};
  const load = obj(raw.load) ?? {};
  return {
    model: str(raw.model) ?? "",
    typology: str(raw.typology),
    points: strings(raw.points),
    modelVersionId: str(raw.model_version_id),
    skipped: str(raw.skipped),
    family: str(raw.family),
    final: {
      train: num(final.train),
      positives: num(final.positives ?? raw.positives),
      rounds: num(final.rounds),
    },
    folds: list(raw.folds).flatMap((item) => {
      const parsed = fold(item);
      return parsed === null ? [] : [parsed];
    }),
    candidates: variants(raw.candidates),
    test: metrics(raw.test),
    byChannel: metricsMap(raw.by_channel),
    separateByChannel: metricsMap(raw.f2_per_channel),
    ablation: variants(raw.ablation),
    strict: {
      status: str(strict.status),
      test: metrics(strict.test),
      positivesTrainByFold: list(strict.positives_train_by_fold).flatMap((item) => {
        const value = num(item);
        return value === null ? [] : [value];
      }),
    },
    fairness: {
      threshold: num(fairness.threshold),
      groups: FAIRNESS_GROUPS.flatMap((key) => {
        const group = obj(fairness[key]);
        return group === null
          ? []
          : [{ key, falsePositiveRate: numberMap(group.false_positive_rate), maxGap: num(group.max_gap) }];
      }),
    },
    load: {
      days: num(load.days),
      worstDay: str(load.worst_day),
      worstDayFlagged: num(load.worst_day_flagged),
      worstDayApplications: num(load.worst_day_applications),
      meanPerDay: num(load.mean_flagged_per_day),
      p95PerDay: num(load.p95_flagged_per_day),
    },
  };
}

function pointInTime(value: unknown): PointInTime | null {
  const check = obj(value);
  if (check === null) return null;
  return {
    checked: num(check.checked),
    mismatched: num(check.mismatched),
    byFeature: numberMap(check.by_feature),
  };
}

export function parseQualityReport(report: Json): QualityReport {
  return {
    config: str(report.config),
    featureSet: str(report.feature_set),
    cutoff: str(report.cutoff),
    examples: num(report.examples),
    f2Mode: str(report.f2_mode),
    pointInTime: pointInTime(report.point_in_time),
    models: list(report.models).flatMap((item) => {
      const raw = obj(item);
      return raw === null ? [] : [modelReport(raw)];
    }),
  };
}

export { metrics as parseMetrics };
