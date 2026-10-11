// «/risk/network» — сеть кредиторов: вкл/выкл со вторым подписантом, правила, ответы сети и счётчики оператора.
import { lenderCounters, networkRules, useNetworkOverview } from "@/entities/network";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { NetworkDecisions } from "@/widgets/risk-network/NetworkDecisions";
import { NetworkRules } from "@/widgets/risk-network/NetworkRules";
import { NetworkState } from "@/widgets/risk-network/NetworkState";
import { OperatorCounters } from "@/widgets/risk-network/OperatorCounters";

import styles from "./PolicyPage.module.css";

const t = ru.risk.network;

function Network() {
  const overview = useNetworkOverview();
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
  return (
    <div className={styles.page}>
      <div className={styles.columns}>
        <NetworkState overview={overview.data} />
        <NetworkDecisions counts={overview.data.decisions} />
      </div>
      <NetworkRules rules={networkRules(overview.data)} />
      <OperatorCounters rows={lenderCounters(overview.data)} />
    </div>
  );
}

export function NetworkPage() {
  return (
    <>
      <PageHeader title={t.title} subtitle={t.subtitle} />
      <Network />
    </>
  );
}
