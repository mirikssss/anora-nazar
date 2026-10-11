// Правила сети действующей политики: сигнал, счётчик оператора, с какого значения срабатывает и уровень.
import { LevelBadge } from "@/entities/decision";
import type { NetworkRule } from "@/entities/network";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { ru } from "@/shared/i18n/ru";
import { formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./RiskNetwork.module.css";

const t = ru.risk.network;

export function NetworkRules({ rules }: { rules: readonly NetworkRule[] }) {
  const reasons = useStaffTexts().data?.reasons;
  const columns: Column<NetworkRule>[] = [
    {
      key: "rule",
      header: t.rule,
      primary: true,
      render: (rule) => (
        <span className={styles.stacked}>
          <span>{titleOf(reasons, rule.code)}</span>
          <code className={styles.code}>{rule.counter}</code>
        </span>
      ),
    },
    {
      key: "min",
      header: t.threshold,
      align: "end",
      render: (rule) =>
        rule.min === null ? (
          ru.common.none
        ) : (
          <span className="num">{`${t.from} ${formatNumber(rule.min)}`}</span>
        ),
    },
    {
      key: "level",
      header: t.level,
      render: (rule) =>
        rule.level === null ? (
          <Badge tone="outline" dot>
            {t.evidenceOnly}
          </Badge>
        ) : (
          <LevelBadge level={rule.level} compact />
        ),
    },
  ];
  return (
    <Card title={t.rulesTitle} subtitle={t.rulesSubtitle} flush>
      <Table caption={t.rulesTitle} columns={columns} rows={rules} rowKey={(rule) => rule.code} />
    </Card>
  );
}
