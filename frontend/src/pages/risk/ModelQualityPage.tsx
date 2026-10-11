// «/risk/models» — качество моделей на отложенной выборке, версии, выпуски со вторым подписантом, обучение.
import { useId } from "react";
import { useSearchParams } from "react-router";

import { parseQualityReport, useQualityReport } from "@/entities/model";
import { ApiError, errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatDate, formatDateTime, formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Tabs } from "@/shared/ui/Tabs";
import { ModelQuality, PointInTimeCheck } from "@/widgets/model-quality/ModelQuality";
import { ModelVersions } from "@/widgets/model-versions/ModelVersions";
import { PendingReleases } from "@/widgets/model-versions/PendingReleases";
import { TrainingRuns } from "@/widgets/risk-training/TrainingRuns";

import styles from "./ModelQualityPage.module.css";

const t = ru.models;
const SELECTED = "model";

function Report() {
  const report = useQualityReport();
  const [params, setParams] = useSearchParams();
  const panelId = useId();

  if (report.isPending) return <Skeleton rows={6} label={t.loading} />;
  if (report.isError) {
    const missing = report.error instanceof ApiError && report.error.status === 404;
    return missing ? (
      <StateMessage title={t.noReport} description={t.noReportHint} />
    ) : (
      <StateMessage
        tone="error"
        title={ru.errors.loadFailed}
        description={errorMessage(report.error)}
        action={
          <Button size="sm" onClick={() => void report.refetch()}>
            {ru.common.retry}
          </Button>
        }
      />
    );
  }

  const parsed = parseQualityReport(report.data.report);
  const selected = parsed.models.find((model) => model.model === params.get(SELECTED)) ?? parsed.models[0];
  const meta = [
    `${t.reportMeta} ${formatDateTime(report.data.created_at)}`,
    parsed.cutoff !== null ? `${t.cutoff} ${formatDate(parsed.cutoff)}` : null,
    parsed.examples !== null ? `${t.examples} ${formatNumber(parsed.examples)}` : null,
    parsed.f2Mode !== null ? `${t.f2Mode}: ${label(t.f2Modes, parsed.f2Mode)}` : null,
    parsed.featureSet !== null ? `${t.featureSet} ${parsed.featureSet}` : null,
    parsed.config !== null ? `${t.config} ${parsed.config}` : null,
  ].filter((item): item is string => item !== null);

  return (
    <section className={styles.report}>
      <p className={styles.meta}>{meta.join(" · ")}</p>
      {parsed.pointInTime !== null ? <PointInTimeCheck check={parsed.pointInTime} /> : null}
      {selected === undefined ? (
        <StateMessage title={t.noReport} />
      ) : (
        <>
          <Tabs
            label={t.tabsLabel}
            panelId={panelId}
            selected={selected.model}
            items={parsed.models.map((model) => ({
              key: model.model,
              label: [model.typology, model.model].filter(Boolean).join(" · "),
            }))}
            onSelect={(key) => {
              setParams({ [SELECTED]: key }, { replace: true });
            }}
          />
          <div id={panelId} role="tabpanel">
            <ModelQuality report={selected} />
          </div>
        </>
      )}
    </section>
  );
}

export function ModelQualityPage() {
  return (
    <>
      <PageHeader
        title={t.title}
        subtitle={t.subtitle}
        tag={<Badge tone="outline">{ru.common.synthetic}</Badge>}
      />
      <div className={styles.page}>
        <Report />
        <ModelVersions />
        <div className={styles.pair}>
          <PendingReleases />
          <TrainingRuns />
        </div>
      </div>
    </>
  );
}
