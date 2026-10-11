// Дрейф признаков: PSI недавнего окна против эталонного и объёмы обоих окон. Порогов тревоги у PSI
// в конфигурации узла нет, поэтому полоса только сравнивает признаки между собой — без оценки цветом.
import type { Drift } from "@/entities/risk";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { ru } from "@/shared/i18n/ru";
import { formatDecimal, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";
import { ValueBar } from "@/shared/ui/ValueBar";

const t = ru.risk.overview;
const PSI_DIGITS = 3;

export function DriftTable({ drift }: { drift: readonly Drift[] }) {
  const features = useStaffTexts().data?.features;
  const max = Math.max(0, ...drift.map((row) => row.psi ?? 0));
  const columns: Column<Drift>[] = [
    { key: "feature", header: t.feature, primary: true, render: (row) => titleOf(features, row.feature) },
    {
      key: "psi",
      header: t.psi,
      align: "end",
      render: (row) =>
        row.psi === null ? (
          t.fewData
        ) : (
          <ValueBar value={row.psi} max={max} text={formatDecimal(row.psi, PSI_DIGITS)} />
        ),
    },
    {
      key: "reference",
      header: t.reference,
      align: "end",
      render: (row) => <span className="num">{formatNumber(row.reference)}</span>,
    },
    {
      key: "recent",
      header: t.recent,
      align: "end",
      render: (row) => <span className="num">{formatNumber(row.recent)}</span>,
    },
  ];
  return (
    <Card title={t.driftTitle} subtitle={t.driftSubtitle} flush>
      {drift.length === 0 ? (
        <StateMessage title={t.driftEmpty} />
      ) : (
        <Table caption={t.driftTitle} columns={columns} rows={drift} rowKey={(row) => row.feature} />
      )}
    </Card>
  );
}
