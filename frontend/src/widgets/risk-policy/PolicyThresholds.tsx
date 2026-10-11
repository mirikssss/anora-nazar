// Действующая политика контура: версия, хеш и пороги, которые меняются через второго подписанта.
import { formatThreshold, thresholdTitle, type PolicyOverview, type Threshold } from "@/entities/policy";
import { ru } from "@/shared/i18n/ru";
import { shortHash } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { SummaryList } from "@/shared/ui/SummaryList";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./RiskPolicy.module.css";

const t = ru.risk.policy;

const columns: Column<Threshold>[] = [
  {
    key: "threshold",
    header: t.threshold,
    primary: true,
    render: (threshold) => (
      <span className={styles.stacked}>
        <span>{thresholdTitle(threshold.path)}</span>
        <code className={styles.code}>{threshold.path}</code>
      </span>
    ),
  },
  {
    key: "value",
    header: t.value,
    align: "end",
    render: (threshold) => <span className="num">{formatThreshold(threshold.value)}</span>,
  },
];

export function PolicyThresholds({ policy }: { policy: PolicyOverview }) {
  return (
    <Card title={t.thresholdsTitle} flush>
      <div className={styles.version}>
        <SummaryList
          rows={[
            { key: "version", label: t.activeVersion, value: policy.active_version },
            {
              key: "hash",
              label: t.hash,
              value: (
                <code className={styles.code} title={policy.policy_hash}>
                  {shortHash(policy.policy_hash, 16)}
                </code>
              ),
            },
          ]}
        />
      </div>
      <Table
        caption={t.thresholdsTitle}
        columns={columns}
        rows={policy.thresholds}
        rowKey={(threshold) => threshold.path}
      />
    </Card>
  );
}
