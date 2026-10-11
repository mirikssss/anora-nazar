// Решения контура по ответу сети: ответила, недоступна (решение по своим данным), выключена.
import { ru, label } from "@/shared/i18n/ru";
import { formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList } from "@/shared/ui/SummaryList";

const t = ru.risk.network;

export function NetworkDecisions({ counts }: { counts: Readonly<Record<string, number>> }) {
  const codes = [...new Set([...Object.keys(t.statuses), ...Object.keys(counts)])];
  const total = codes.reduce((sum, code) => sum + (counts[code] ?? 0), 0);
  return (
    <Card title={t.decisionsTitle}>
      {total === 0 ? (
        <StateMessage title={t.decisionsEmpty} />
      ) : (
        <SummaryList
          rows={codes.map((code) => ({
            key: code,
            label: label(t.statuses, code),
            value: <span className="num">{formatNumber(counts[code] ?? 0)}</span>,
          }))}
        />
      )}
    </Card>
  );
}
