// Счётчики оператора по кредитору и контуру: что принято, сколько запросов узла и уведомлений.
import type { LenderCounters } from "@/entities/network";
import { label, ru } from "@/shared/i18n/ru";
import { formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./RiskNetwork.module.css";

const t = ru.risk.network;

function count(value: number) {
  return <span className="num">{formatNumber(value)}</span>;
}

const COLUMNS: readonly Column<LenderCounters>[] = [
  {
    key: "lender",
    header: t.lender,
    primary: true,
    render: (row) => (
      <span className={styles.stacked}>
        <span>{label(t.lenders, row.lender)}</span>
        <span className={styles.muted}>{label(t.contours, row.contour)}</span>
      </span>
    ),
  },
  { key: "applications", header: t.applications, align: "end", render: (row) => count(row.applications) },
  { key: "events", header: t.events, align: "end", render: (row) => count(row.events) },
  { key: "confirmed", header: t.confirmed, align: "end", render: (row) => count(row.confirmedResults) },
  { key: "queries", header: t.queries, align: "end", render: (row) => count(row.queries) },
  {
    key: "quota",
    header: t.quota,
    align: "end",
    render: (row) => (
      <span className="num">
        {row.quotaLimit === null
          ? formatNumber(row.quotaUsed)
          : `${formatNumber(row.quotaUsed)} ${t.quotaOf} ${formatNumber(row.quotaLimit)}`}
      </span>
    ),
  },
  { key: "watches", header: t.watches, align: "end", render: (row) => count(row.activeWatches) },
  {
    key: "delivered",
    header: t.delivered,
    align: "end",
    render: (row) => (
      <span className={styles.stacked}>
        {count(row.delivered)}
        {row.pending > 0 ? (
          <span className={styles.muted}>{`${t.notificationsPending} ${formatNumber(row.pending)}`}</span>
        ) : null}
        {row.failed > 0 ? (
          <span className={styles.muted}>{`${t.notificationsFailed} ${formatNumber(row.failed)}`}</span>
        ) : null}
      </span>
    ),
  },
];

export function OperatorCounters({ rows }: { rows: readonly LenderCounters[] | null }) {
  return (
    <Card title={t.countersTitle} subtitle={t.countersSubtitle} flush>
      {rows === null ? (
        <StateMessage tone="error" title={t.operatorDown} description={t.operatorDownHint} />
      ) : rows.length === 0 ? (
        <StateMessage title={t.countersEmpty} />
      ) : (
        <Table
          caption={t.countersTitle}
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => `${row.contour}:${row.lender}`}
        />
      )}
    </Card>
  );
}
