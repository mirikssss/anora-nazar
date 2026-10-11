// Качество одной модели: скользящая проверка по времени, абляция, кандидаты, окна, предельная изоляция
// групп, выпускаемая модель, справедливость и нагрузка проверки.
import type { ReactNode } from "react";

import {
  formatBrier,
  formatCount,
  formatPrAuc,
  formatRate,
  formatScore,
  type Metrics,
  type ModelReport,
  type PointInTime,
  type ReviewPoint,
  type Variant,
} from "@/entities/model";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { label, ru } from "@/shared/i18n/ru";
import { formatDate, formatDecimal } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";
import { Table, type Column } from "@/shared/ui/Table";
import { ValueBar } from "@/shared/ui/ValueBar";

import styles from "./ModelQuality.module.css";

const t = ru.models;

/** Доли проверки — как пришли с бэка, в порядке первой встреченной метрики. */
function reviewShares(metrics: readonly (Metrics | null)[]): string[] {
  return [...new Set(metrics.flatMap((m) => m?.review.map((point) => point.share) ?? []))];
}

function reviewAt(metrics: Metrics | null, share: string): ReviewPoint | null {
  return metrics?.review.find((point) => point.share === share) ?? null;
}

function count(value: number | null, positives: number | null): string {
  return `${formatCount(value)} / ${formatCount(positives)} ${t.positivesOf}`;
}

interface MetricRow {
  key: string;
  title: string;
  value: (metrics: Metrics | null) => string;
}

function metricRows(shares: readonly string[]): MetricRow[] {
  const review =
    (share: string, pick: (point: ReviewPoint) => number | null, format: typeof formatRate) =>
    (metrics: Metrics | null) => {
      const point = reviewAt(metrics, share);
      return format(point === null ? null : pick(point));
    };
  return [
    {
      key: "applications",
      title: t.metricNames.applications,
      value: (m) => formatCount(m?.applications ?? null),
    },
    { key: "positives", title: t.metricNames.positives, value: (m) => formatCount(m?.positives ?? null) },
    { key: "prAuc", title: t.metricNames.prAuc, value: formatPrAuc },
    { key: "random", title: t.metricNames.randomPrAuc, value: (m) => formatScore(m?.randomPrAuc ?? null) },
    ...shares.flatMap((share) => [
      {
        key: `reviewed-${share}`,
        title: `${t.reviewNames.reviewed} ${share}`,
        value: review(share, (p) => p.reviewed, formatCount),
      },
      {
        key: `recall-${share}`,
        title: `${t.reviewNames.recall} ${share}`,
        value: review(share, (p) => p.recall, formatRate),
      },
      {
        key: `precision-${share}`,
        title: `${t.reviewNames.precision} ${share}`,
        value: review(share, (p) => p.precision, formatRate),
      },
      {
        key: `false-${share}`,
        title: `${t.reviewNames.falseReviewShare} ${share}`,
        value: review(share, (p) => p.falseReviewShare, formatRate),
      },
    ]),
    { key: "fpr", title: t.metricNames.recallAtFpr, value: (m) => formatRate(m?.recallAtFpr ?? null) },
    { key: "brier", title: t.metricNames.brier, value: (m) => formatBrier(m?.brier ?? null) },
  ];
}

function MetricsCard({ report }: { report: ModelReport }) {
  const channels = Object.entries(report.byChannel);
  // Канал один — его колонка повторяла бы «Всего».
  const columns = [
    { key: "total", title: t.total, metrics: report.test },
    ...(channels.length > 1
      ? channels.map(([channel, metrics]) => ({ key: channel, title: label(ru.channels, channel), metrics }))
      : []),
  ];
  const tableColumns: Column<MetricRow>[] = [
    { key: "metric", header: t.metric, primary: true, render: (row) => row.title },
    ...columns.map((column) => ({
      key: column.key,
      header: column.title,
      align: "end" as const,
      render: (row: MetricRow) => <span className="num">{row.value(column.metrics)}</span>,
    })),
  ];
  const rows = metricRows(reviewShares(columns.map((column) => column.metrics)));
  return (
    <Card title={t.metricsTitle} subtitle={t.metricsSubtitle} flush>
      <Table caption={t.metricsTitle} columns={tableColumns} rows={rows} rowKey={(row) => row.key} />
    </Card>
  );
}

/** Таблица вариантов: PR-AUC полосой, интервал, recall при каждой доле проверки. */
function VariantTable({
  caption,
  variants,
  titleOf,
  emphasis,
  extra = [],
}: {
  caption: string;
  variants: readonly Variant[];
  titleOf: (variant: Variant) => ReactNode;
  emphasis: (variant: Variant) => boolean;
  extra?: readonly Column<Variant>[];
}) {
  const max = Math.max(0, ...variants.map((variant) => variant.metrics?.prAuc ?? 0));
  const shares = reviewShares(variants.map((variant) => variant.metrics));
  const statusOr = (variant: Variant, render: (metrics: Metrics) => ReactNode) =>
    variant.metrics === null ? (
      <span className={styles.muted}>
        {variant.status === null ? ru.common.none : label(t.variantStatuses, variant.status)}
      </span>
    ) : (
      render(variant.metrics)
    );
  const columns: Column<Variant>[] = [
    { key: "variant", header: t.variant, primary: true, render: titleOf },
    {
      key: "prAuc",
      header: t.prAuc,
      align: "end",
      render: (variant) =>
        statusOr(variant, (metrics) => (
          <ValueBar
            value={metrics.prAuc}
            max={max}
            text={formatScore(metrics.prAuc)}
            emphasis={emphasis(variant)}
          />
        )),
    },
    {
      key: "ci",
      header: t.ci,
      align: "end",
      render: (variant) => {
        const ci = variant.metrics?.prAucCi ?? null;
        return ci === null ? ru.common.none : `${formatScore(ci[0])} – ${formatScore(ci[1])}`;
      },
    },
    ...shares.map((share) => ({
      key: `recall-${share}`,
      header: `${t.recallAt} ${share}`,
      align: "end" as const,
      render: (variant: Variant) => formatRate(reviewAt(variant.metrics, share)?.recall ?? null),
    })),
    ...extra,
  ];
  return <Table caption={caption} columns={columns} rows={variants} rowKey={(variant) => variant.key} />;
}

function AblationCard({ report }: { report: ModelReport }) {
  if (report.ablation.length === 0) return null;
  return (
    <Card title={t.ablationTitle} subtitle={t.ablationSubtitle} flush>
      <VariantTable
        caption={t.ablationTitle}
        variants={report.ablation}
        titleOf={(variant) => label(t.variants, variant.key)}
        emphasis={(variant) => variant.key === "with_graph"}
      />
    </Card>
  );
}

function CandidatesCard({ report }: { report: ModelReport }) {
  if (report.candidates.length === 0) return null;
  const chosen = (variant: Variant) => variant.key === report.family;
  return (
    <Card title={t.candidatesTitle} subtitle={t.candidatesSubtitle} flush>
      <VariantTable
        caption={t.candidatesTitle}
        variants={report.candidates}
        titleOf={(variant) => (
          <span className={styles.candidate}>
            {label(t.families, variant.key)}
            {chosen(variant) ? <Badge tone="outline">{t.chosen}</Badge> : null}
          </span>
        )}
        emphasis={chosen}
        extra={[
          {
            key: "brier",
            header: t.metricNames.brier,
            align: "end",
            render: (variant) => formatBrier(variant.metrics?.brier ?? null),
          },
        ]}
      />
    </Card>
  );
}

interface FoldRow {
  index: number;
  fold: ModelReport["folds"][number];
}

function FoldsCard({ report }: { report: ModelReport }) {
  if (report.folds.length === 0) return null;
  const rows: FoldRow[] = report.folds.map((fold, index) => ({ index, fold }));
  const columns: Column<FoldRow>[] = [
    { key: "fold", header: t.fold, primary: true, render: (row) => `${t.fold} ${row.index + 1}` },
    {
      key: "from",
      header: t.testFrom,
      render: (row) => (row.fold.testFrom === null ? ru.common.none : formatDate(row.fold.testFrom)),
    },
    {
      key: "train",
      header: t.train,
      align: "end",
      render: (row) => count(row.fold.train, row.fold.positivesTrain),
    },
    {
      key: "test",
      header: t.test,
      align: "end",
      render: (row) => count(row.fold.test, row.fold.positivesTest),
    },
    {
      key: "excluded",
      header: t.excluded,
      align: "end",
      render: (row) => formatCount(row.fold.excludedFromTraining),
    },
    {
      key: "suppliers",
      header: t.heldOutSuppliers,
      align: "end",
      render: (row) => formatCount(row.fold.heldOutSuppliers),
    },
  ];
  return (
    <Card title={t.foldsTitle} subtitle={t.foldsSubtitle} flush>
      <Table caption={t.foldsTitle} columns={columns} rows={rows} rowKey={(row) => String(row.index)} />
    </Card>
  );
}

interface ChannelRow {
  channel: string;
  shared: Metrics | null;
  separate: Metrics;
}

function SeparateCard({ report }: { report: ModelReport }) {
  const rows: ChannelRow[] = Object.entries(report.separateByChannel).map(([channel, separate]) => ({
    channel,
    shared: report.byChannel[channel] ?? null,
    separate,
  }));
  if (rows.length === 0) return null;
  const columns: Column<ChannelRow>[] = [
    { key: "channel", header: t.channel, primary: true, render: (row) => label(ru.channels, row.channel) },
    {
      key: "shared",
      header: `${t.metricNames.prAuc} · ${t.shared}`,
      align: "end",
      render: (row) => formatPrAuc(row.shared),
    },
    {
      key: "separate",
      header: `${t.metricNames.prAuc} · ${t.separate}`,
      align: "end",
      render: (row) => formatPrAuc(row.separate),
    },
  ];
  return (
    <Card title={t.separateTitle} subtitle={t.separateSubtitle} flush>
      <Table caption={t.separateTitle} columns={columns} rows={rows} rowKey={(row) => row.channel} />
    </Card>
  );
}

function reviewRows(metrics: Metrics | null): SummaryRow[] {
  return (metrics?.review ?? []).map((point) => ({
    key: `recall-${point.share}`,
    label: `${t.reviewNames.recall} ${point.share}`,
    value: formatRate(point.recall),
  }));
}

function FinalCard({ report }: { report: ModelReport }) {
  return (
    <Card title={t.finalTitle} subtitle={t.finalSubtitle}>
      <SummaryList
        rows={[
          {
            key: "family",
            label: t.family,
            value: report.family === null ? ru.common.none : label(t.families, report.family),
          },
          { key: "train", label: t.finalTrain, value: formatCount(report.final.train) },
          { key: "positives", label: t.finalPositives, value: formatCount(report.final.positives) },
          ...(report.final.rounds === null
            ? []
            : [{ key: "rounds", label: t.rounds, value: formatCount(report.final.rounds) }]),
        ]}
      />
    </Card>
  );
}

function StrictCard({ report }: { report: ModelReport }) {
  const { strict } = report;
  if (strict.status === null) return null;
  return (
    <Card title={t.strictTitle} subtitle={t.strictSubtitle}>
      <SummaryList
        rows={[
          { key: "status", label: t.strictStatus, value: label(t.variantStatuses, strict.status) },
          {
            key: "positives",
            label: t.positivesTrainByFold,
            value: strict.positivesTrainByFold.map(formatCount).join(" · ") || ru.common.none,
          },
          ...(strict.test === null
            ? []
            : [
                { key: "prAuc", label: t.metricNames.prAuc, value: formatPrAuc(strict.test) },
                {
                  key: "random",
                  label: t.metricNames.randomPrAuc,
                  value: formatScore(strict.test.randomPrAuc),
                },
                ...reviewRows(strict.test),
              ]),
        ]}
      />
    </Card>
  );
}

function FairnessCard({ report }: { report: ModelReport }) {
  const { groups } = report.fairness;
  if (groups.length === 0) return null;
  const max = Math.max(...groups.flatMap((group) => Object.values(group.falsePositiveRate)));
  return (
    <Card title={t.fairnessTitle} subtitle={t.fairnessSubtitle}>
      <div className={styles.groups}>
        {groups.map((group) => (
          <section key={group.key} className={styles.group}>
            <h3 className={styles.groupTitle}>{label(t.fairnessGroups, group.key)}</h3>
            <SummaryList
              rows={[
                ...Object.entries(group.falsePositiveRate).map(([value, rate]) => ({
                  key: value,
                  label: label(t.fairnessValues, value),
                  value: <ValueBar value={rate} max={max} text={formatRate(rate)} />,
                })),
                { key: "gap", label: t.maxGap, value: formatRate(group.maxGap) },
              ]}
            />
          </section>
        ))}
      </div>
    </Card>
  );
}

function LoadCard({ report }: { report: ModelReport }) {
  const { load } = report;
  const perDay = (value: number | null) => (value === null ? ru.common.none : formatDecimal(value, 1));
  return (
    <Card title={t.loadTitle} subtitle={t.loadSubtitle}>
      <SummaryList
        rows={[
          {
            key: "worst",
            label: t.worstDay,
            value:
              load.worstDay === null
                ? ru.common.none
                : `${formatDate(load.worstDay)} · ${formatCount(load.worstDayFlagged)} ${t.worstDayValue} ${formatCount(load.worstDayApplications)}`,
          },
          { key: "p95", label: t.loadP95, value: perDay(load.p95PerDay) },
          { key: "mean", label: t.loadMean, value: perDay(load.meanPerDay) },
          { key: "days", label: t.loadDays, value: formatCount(load.days) },
        ]}
      />
    </Card>
  );
}

export function ModelQuality({ report }: { report: ModelReport }) {
  if (report.skipped !== null) {
    return (
      <div className={styles.stack}>
        <StateMessage title={t.skipped} description={label(t.skippedReasons, report.skipped)} />
        <FoldsCard report={report} />
      </div>
    );
  }
  return (
    <div className={styles.columns}>
      <div className={styles.stack}>
        <MetricsCard report={report} />
        <AblationCard report={report} />
        <CandidatesCard report={report} />
        <FoldsCard report={report} />
        <SeparateCard report={report} />
      </div>
      <div className={styles.stack}>
        <FinalCard report={report} />
        <StrictCard report={report} />
        <LoadCard report={report} />
        <FairnessCard report={report} />
      </div>
    </div>
  );
}

/** Проверка point-in-time на весь отчёт: признаки прошлых решений, пересчитанные на их момент. */
export function PointInTimeCheck({ check }: { check: PointInTime }) {
  const features = useStaffTexts().data?.features;
  const intact = check.mismatched === 0;
  return (
    <Card
      title={t.pointInTimeTitle}
      subtitle={t.pointInTimeSubtitle}
      actions={
        check.mismatched === null ? undefined : (
          <Badge tone={intact ? "green" : "red"} dot>
            {intact ? t.pointInTimeOk : t.pointInTimeBroken}
          </Badge>
        )
      }
    >
      <SummaryList
        rows={[
          { key: "checked", label: t.checked, value: formatCount(check.checked) },
          { key: "mismatched", label: t.mismatched, value: formatCount(check.mismatched) },
          ...Object.entries(check.byFeature).map(([feature, mismatches]) => ({
            key: feature,
            label: titleOf(features, feature),
            value: formatCount(mismatches),
          })),
        ]}
      />
    </Card>
  );
}
