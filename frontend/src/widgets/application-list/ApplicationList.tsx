// Заявки песочницы с ответом узла: сумма, канал, уровень, статус.
import { lastDecision, snapshotView, useApplications, type Application } from "@/entities/application";
import { LevelBadge } from "@/entities/decision";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatSum, formatTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

const t = ru.application;

const COLUMNS: readonly Column<Application>[] = [
  { key: "id", header: t.id, primary: true, render: (app) => app.id },
  { key: "channel", header: t.channel, render: (app) => label(ru.channels, app.channel) },
  {
    key: "amount",
    header: t.amount,
    align: "end",
    render: (app) => {
      const amount = snapshotView(app).amount;
      return amount !== null ? formatSum(amount) : ru.common.none;
    },
  },
  {
    key: "level",
    header: t.level,
    render: (app) => <LevelBadge level={lastDecision(app)?.level ?? null} compact />,
  },
  {
    key: "status",
    header: t.status,
    render: (app) =>
      app.node_state !== null ? (
        <Badge tone="orange" dot>
          {label(ru.nodeStates, app.node_state)}
        </Badge>
      ) : (
        label(ru.applicationStatuses, app.status)
      ),
  },
  { key: "version", header: t.version, align: "end", render: (app) => app.version },
  { key: "updated", header: t.updated, align: "end", render: (app) => formatTime(app.updated_at) },
];

interface ApplicationListProps {
  selectedId: string | null;
  onSelect: (application: Application) => void;
}

export function ApplicationList({ selectedId, onSelect }: ApplicationListProps) {
  const applications = useApplications();
  return (
    <Card title={t.listTitle} flush>
      {applications.isPending ? (
        <Skeleton rows={4} label={t.loading} />
      ) : applications.isError ? (
        <StateMessage
          tone="error"
          title={ru.errors.loadFailed}
          description={errorMessage(applications.error)}
          action={
            <Button size="sm" onClick={() => void applications.refetch()}>
              {ru.common.retry}
            </Button>
          }
        />
      ) : applications.data.length === 0 ? (
        <StateMessage title={t.listEmpty} description={t.listEmptyHint} />
      ) : (
        <Table
          caption={t.listTitle}
          columns={COLUMNS}
          rows={applications.data}
          rowKey={(app) => app.id}
          selectedKey={selectedId}
          onRowClick={onSelect}
        />
      )}
    </Card>
  );
}
