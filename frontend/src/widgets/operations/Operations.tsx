// Операции АБС: статус по ключу бизнес-операции; у выбранной — разрешение узла или отказ с причиной.
import { useOperations, type Operation } from "@/entities/operation";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatSum, formatTime, formatValue, shortHash } from "@/shared/lib/format";
import { Badge, type BadgeTone } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./Operations.module.css";

const t = ru.coreBanking;

const STATUS_TONES: Readonly<Record<string, BadgeTone>> = {
  executed: "green",
  refused: "red",
  not_executed: "orange",
  waiting_node: "orange",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={STATUS_TONES[status] ?? "neutral"} dot>
      {label(ru.operationStatuses, status)}
    </Badge>
  );
}

const COLUMNS: readonly Column<Operation>[] = [
  { key: "key", header: t.key, primary: true, render: (op) => <code>{op.operation_key}</code> },
  { key: "type", header: t.operationType, render: (op) => label(ru.operationTypes, op.operation_type) },
  { key: "amount", header: t.amount, align: "end", render: (op) => formatSum(op.amount) },
  { key: "status", header: t.status, render: (op) => <StatusBadge status={op.status} /> },
  {
    key: "reported",
    header: t.outcomeReported,
    render: (op) => (op.outcome_reported ? ru.common.yes : ru.common.no),
  },
  { key: "time", header: t.time, align: "end", render: (op) => formatTime(op.updated_at) },
];

function objectRows(prefix: string, value: Record<string, unknown>): SummaryRow[] {
  return Object.entries(value).map(([key, item]) => ({
    key: `${prefix}-${key}`,
    label: key,
    value: formatValue(item),
  }));
}

function OperationDetail({ operation }: { operation: Operation }) {
  const rows: SummaryRow[] = [
    { key: "application", label: t.application, value: operation.application_id },
    { key: "version", label: ru.common.version, value: operation.application_version },
    { key: "tranche", label: t.tranche, value: operation.tranche },
    { key: "account", label: t.account, value: operation.account },
    { key: "created", label: t.time, value: formatDateTime(operation.created_at) },
  ];
  const permit = operation.permit;
  const refusal = operation.refusal;
  return (
    <div className={styles.detail}>
      <SummaryList rows={rows} />
      {permit !== null ? (
        <section className={styles.section}>
          <h3 className={styles.heading}>{t.permit}</h3>
          <SummaryList
            rows={[
              ...(typeof permit.payload === "object" && permit.payload !== null
                ? objectRows("permit", permit.payload as Record<string, unknown>)
                : []),
              {
                key: "signature",
                label: t.signature,
                value: (
                  <code title={formatValue(permit.signature)}>
                    {shortHash(formatValue(permit.signature), 24)}
                  </code>
                ),
              },
              { key: "key-id", label: t.keyId, value: formatValue(permit.key_id) },
            ]}
          />
        </section>
      ) : null}
      {refusal !== null ? (
        <section className={styles.section}>
          <h3 className={styles.heading}>{t.refusal}</h3>
          <p className={styles.refusal}>{formatValue(refusal.message)}</p>
          <SummaryList rows={objectRows("refusal", refusal).filter((row) => row.label !== "message")} />
        </section>
      ) : null}
    </div>
  );
}

interface OperationsProps {
  selectedKey: string | null;
  onSelect: (operation: Operation) => void;
}

export function Operations({ selectedKey, onSelect }: OperationsProps) {
  const operations = useOperations();
  const selected = operations.data?.find((op) => op.operation_key === selectedKey) ?? null;
  return (
    <>
      <Card title={t.operationsTitle} flush>
        {operations.isPending ? (
          <Skeleton rows={4} label={t.loading} />
        ) : operations.isError ? (
          <StateMessage
            tone="error"
            title={ru.errors.loadFailed}
            description={errorMessage(operations.error)}
            action={
              <Button size="sm" onClick={() => void operations.refetch()}>
                {ru.common.retry}
              </Button>
            }
          />
        ) : operations.data.length === 0 ? (
          <StateMessage title={t.operationsEmpty} />
        ) : (
          <Table
            caption={t.operationsTitle}
            columns={COLUMNS}
            rows={operations.data}
            rowKey={(op) => op.operation_key}
            selectedKey={selectedKey}
            onRowClick={onSelect}
          />
        )}
      </Card>
      {selected !== null ? (
        <Card title={selected.operation_key} actions={<StatusBadge status={selected.status} />}>
          <OperationDetail operation={selected} />
        </Card>
      ) : operations.data !== undefined && operations.data.length > 0 ? (
        <StateMessage title={t.select} />
      ) : null}
    </>
  );
}
