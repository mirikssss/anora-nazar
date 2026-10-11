// «/decisions/:decisionId» — решение: причины, версии, воспроизведение.
import { useParams } from "react-router";

import { parseRecord, useDecisionRecord } from "@/entities/decision";
import { hasPermission, useSession } from "@/entities/session";
import { DecisionReplay } from "@/features/decision-replay";
import { ApiError, errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatValue, shortHash } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList } from "@/shared/ui/SummaryList";
import { DecisionCard } from "@/widgets/decision-card/DecisionCard";

import styles from "./DecisionPage.module.css";

const t = ru.decision;

export function DecisionPage() {
  const { decisionId = "" } = useParams();
  const session = useSession();
  const record = useDecisionRecord(decisionId);

  if (record.isPending) return <Skeleton rows={6} label={t.loading} />;
  if (record.isError) {
    const notFound = record.error instanceof ApiError && record.error.status === 404;
    return (
      <StateMessage
        tone="error"
        title={notFound ? t.notFound : ru.errors.loadFailed}
        description={notFound ? undefined : errorMessage(record.error)}
        action={
          notFound ? undefined : (
            <Button size="sm" onClick={() => void record.refetch()}>
              {ru.common.retry}
            </Button>
          )
        }
      />
    );
  }

  const parsed = parseRecord(record.data.record);
  const versions = parsed.versions;
  return (
    <>
      <PageHeader
        title={`${t.title} ${shortHash(record.data.decision_id, 8)}`}
        subtitle={`${label(ru.points, record.data.point)} · ${t.asOf} ${formatDateTime(record.data.as_of)} · ${ru.common.version} ${String(record.data.application_version)}`}
      />
      <div className={styles.columns}>
        <Card>
          <DecisionCard result={parsed.result} point={record.data.point} />
        </Card>
        <div className={styles.stack}>
          <Card title={t.versions}>
            <SummaryList
              rows={[
                { key: "policy", label: t.policy, value: versions.policy ?? ru.common.none },
                { key: "reasons", label: t.reasonCatalog, value: versions.reasons ?? ru.common.none },
                { key: "features", label: t.featureSet, value: versions.featureSet ?? ru.common.none },
                { key: "models", label: t.models, value: versions.models.join(", ") || t.noModels },
                {
                  key: "shadow",
                  label: t.shadowModels,
                  value: versions.shadowModels.join(", ") || ru.common.none,
                },
                {
                  key: "hash",
                  label: t.recordHash,
                  value: (
                    <code title={record.data.record_hash}>{shortHash(record.data.record_hash, 20)}</code>
                  ),
                },
              ]}
            />
          </Card>
          <DecisionReplay decisionId={record.data.decision_id} />
          {hasPermission(session, PERMISSIONS.viewQuality) && parsed.features !== null ? (
            <Card title={t.features} subtitle={t.featuresHint}>
              <SummaryList
                rows={Object.entries(parsed.features).map(([key, value]) => ({
                  key,
                  label: <code>{key}</code>,
                  value: formatValue(value),
                }))}
              />
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
