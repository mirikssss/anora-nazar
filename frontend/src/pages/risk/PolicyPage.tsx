// «/risk/policy» — действующие пороги, предложение изменения и подтверждение вторым подписантом.
import { usePolicy } from "@/entities/policy";
import { hasPermission, useSession } from "@/entities/session";
import { ThresholdChange } from "@/features/policy-change";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { PolicyThresholds } from "@/widgets/risk-policy/PolicyThresholds";
import { Proposals } from "@/widgets/risk-policy/Proposals";

import styles from "./PolicyPage.module.css";

const t = ru.risk.policy;

function Policy() {
  const session = useSession();
  const policy = usePolicy();
  if (policy.isPending) return <Skeleton rows={8} label={t.loading} />;
  if (policy.isError) {
    return (
      <StateMessage
        tone="error"
        title={ru.errors.loadFailed}
        description={errorMessage(policy.error)}
        action={
          <Button size="sm" onClick={() => void policy.refetch()}>
            {ru.common.retry}
          </Button>
        }
      />
    );
  }
  const canPropose = hasPermission(session, PERMISSIONS.proposePolicy);
  return (
    <div className={styles.page}>
      <div className={styles.columns}>
        <PolicyThresholds policy={policy.data} />
        {canPropose ? <ThresholdChange thresholds={policy.data.thresholds} /> : null}
      </div>
      <Proposals proposals={policy.data.proposals} />
    </div>
  );
}

export function PolicyPage() {
  return (
    <>
      <PageHeader title={t.title} subtitle={t.subtitle} />
      <Policy />
    </>
  );
}
