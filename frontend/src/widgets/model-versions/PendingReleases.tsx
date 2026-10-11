// Выпуски моделей, ждущие второго подписанта: кто запросил и когда; подтверждает другой сотрудник.
import { approveRelease, modelKeys, usePendingReleases, type Release } from "@/entities/model";
import { useStaffName } from "@/entities/risk";
import { hasPermission, useSession } from "@/entities/session";
import { SecondSignerApproval } from "@/features/risk-approval";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

const t = ru.risk.releases;

export function PendingReleases() {
  const session = useSession();
  const releases = usePendingReleases();
  const staffName = useStaffName();
  const columns: Column<Release>[] = [
    { key: "model", header: t.model, primary: true, render: (release) => release.model_name },
    { key: "by", header: t.requestedBy, render: (release) => staffName(release.requested_by) },
    {
      key: "at",
      header: t.requestedAt,
      align: "end",
      render: (release) => formatDateTime(release.requested_at),
    },
  ];
  if (hasPermission(session, PERMISSIONS.promoteModels)) {
    columns.push({
      key: "approve",
      header: "",
      align: "end",
      render: (release) => (
        <SecondSignerApproval
          requestedBy={release.requested_by}
          approve={() => approveRelease(release.release_id)}
          invalidate={[modelKeys.releases, modelKeys.versions]}
        />
      ),
    });
  }
  return (
    <Card title={t.title} subtitle={t.subtitle} flush>
      {releases.isPending ? (
        <Skeleton rows={2} label={ru.common.loading} />
      ) : releases.isError ? (
        <StateMessage tone="error" title={ru.errors.loadFailed} description={errorMessage(releases.error)} />
      ) : releases.data.length === 0 ? (
        <StateMessage title={t.empty} />
      ) : (
        <Table
          caption={t.title}
          columns={columns}
          rows={releases.data}
          rowKey={(release) => release.release_id}
        />
      )}
    </Card>
  );
}
