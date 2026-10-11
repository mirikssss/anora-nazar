// Записи журнала контура: событие, время, хеш и ссылка на предыдущую запись; у выбранной — содержание.
import { useState } from "react";
import { Link } from "react-router";

import { useAuditRecords, type AuditRecord } from "@/entities/audit";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatTime, formatValue, shortHash } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList } from "@/shared/ui/SummaryList";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./AuditChain.module.css";

const t = ru.audit;

const COLUMNS: readonly Column<AuditRecord>[] = [
  { key: "seq", header: t.seq, align: "end", render: (record) => record.seq },
  { key: "kind", header: t.kind, primary: true, render: (record) => label(ru.auditKinds, record.kind) },
  { key: "time", header: t.recordedAt, render: (record) => formatTime(record.recorded_at, true) },
  {
    key: "hash",
    header: t.hash,
    render: (record) => <code title={record.hash}>{shortHash(record.hash)}</code>,
  },
  {
    key: "prev",
    header: t.prevHash,
    render: (record) => <code title={record.prev_hash}>{shortHash(record.prev_hash)}</code>,
  },
];

export function AuditChain() {
  const records = useAuditRecords();
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);
  const rows = records.data?.pages.flat() ?? [];
  const selected = rows.find((record) => record.seq === selectedSeq) ?? null;

  return (
    <div className={styles.stack}>
      <Card title={t.recordsTitle} flush>
        {records.isPending ? (
          <Skeleton rows={5} label={t.loading} />
        ) : records.isError ? (
          <StateMessage
            tone="error"
            title={ru.errors.loadFailed}
            description={errorMessage(records.error)}
            action={
              <Button size="sm" onClick={() => void records.refetch()}>
                {ru.common.retry}
              </Button>
            }
          />
        ) : rows.length === 0 ? (
          <StateMessage title={t.recordsEmpty} />
        ) : (
          <>
            <Table
              caption={t.recordsTitle}
              columns={COLUMNS}
              rows={rows}
              rowKey={(record) => String(record.seq)}
              selectedKey={selectedSeq === null ? null : String(selectedSeq)}
              onRowClick={(record) => {
                setSelectedSeq(record.seq);
              }}
            />
            {records.hasNextPage ? (
              <div className={styles.more}>
                <Button
                  size="sm"
                  pending={records.isFetchingNextPage}
                  onClick={() => void records.fetchNextPage()}
                >
                  {t.more}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Card>
      {selected !== null ? (
        <Card
          title={`№ ${String(selected.seq)} · ${label(ru.auditKinds, selected.kind)}`}
          subtitle={formatDateTime(selected.recorded_at)}
          actions={
            typeof selected.payload.decision_id === "string" ? (
              <Link to={`/decisions/${selected.payload.decision_id}`}>{ru.application.openDecision}</Link>
            ) : undefined
          }
        >
          <SummaryList
            rows={[
              ...Object.entries(selected.payload).map(([key, value]) => ({
                key,
                label: <code>{key}</code>,
                value: formatValue(value),
              })),
              { key: "__hash", label: t.hash, value: <code>{selected.hash}</code> },
              { key: "__prev", label: t.prevHash, value: <code>{selected.prev_hash}</code> },
            ]}
          />
        </Card>
      ) : null}
    </div>
  );
}
