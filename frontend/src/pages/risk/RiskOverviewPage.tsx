// «/risk» — решения по уровням за последние дни, очереди дел и дрейф признаков контура.
import { useRiskOverview } from "@/entities/risk";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { DriftTable } from "@/widgets/risk-drift/DriftTable";
import { LevelsChart } from "@/widgets/risk-levels/LevelsChart";
import { QueueSummary } from "@/widgets/risk-queues/QueueSummary";

import styles from "./RiskOverviewPage.module.css";

const t = ru.risk.overview;

function Overview() {
  const overview = useRiskOverview();
  if (overview.isPending) return <Skeleton rows={8} label={t.loading} />;
  if (overview.isError) {
    return (
      <StateMessage
        tone="error"
        title={ru.errors.loadFailed}
        description={errorMessage(overview.error)}
        action={
          <Button size="sm" onClick={() => void overview.refetch()}>
            {ru.common.retry}
          </Button>
        }
      />
    );
  }
  const { latest, levels, queues, drift } = overview.data;
  return (
    <div className={styles.page}>
      {latest !== null ? (
        <p className={styles.meta}>
          {t.latest} {formatDateTime(latest)}
        </p>
      ) : null}
      <div className={styles.columns}>
        {levels.length === 0 ? (
          <StateMessage title={t.empty} description={t.emptyHint} />
        ) : (
          <LevelsChart days={levels} />
        )}
        <QueueSummary queues={queues} />
      </div>
      <DriftTable drift={drift} />
    </div>
  );
}

export function RiskOverviewPage() {
  return (
    <>
      <PageHeader
        title={t.title}
        subtitle={t.subtitle}
        tag={<Badge tone="outline">{ru.common.synthetic}</Badge>}
      />
      <Overview />
    </>
  );
}
