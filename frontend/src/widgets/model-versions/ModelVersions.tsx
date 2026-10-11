// Версии моделей в контуре: статус, контракт признаков, качество на тесте; выпуск из тени.
import { formatPrAuc, parseMetrics, useModelVersions, type ModelVersion } from "@/entities/model";
import { hasPermission, useSession } from "@/entities/session";
import { RequestRelease } from "@/features/model-release";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Badge, type BadgeTone } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

const t = ru.models;

const STATUS_TONES: Readonly<Record<string, BadgeTone>> = {
  active: "green",
  shadow: "neutral",
  retired: "outline",
};

export function ModelVersions() {
  const session = useSession();
  const versions = useModelVersions();
  const canPromote = hasPermission(session, PERMISSIONS.promoteModels);
  const columns: Column<ModelVersion>[] = [
    { key: "name", header: t.name, primary: true, render: (model) => model.name },
    { key: "typology", header: t.typology, render: (model) => model.typology },
    { key: "points", header: t.points, render: (model) => model.points.join(", ") },
    { key: "features", header: t.featureSet, render: (model) => model.feature_set_version },
    {
      key: "prAuc",
      header: t.metricNames.prAuc,
      align: "end",
      render: (model) => formatPrAuc(parseMetrics(model.metrics.test)),
    },
    {
      key: "status",
      header: t.status,
      render: (model) => (
        <Badge tone={STATUS_TONES[model.status] ?? "neutral"} dot>
          {label(t.statuses, model.status)}
        </Badge>
      ),
    },
    { key: "created", header: t.created, align: "end", render: (model) => formatDateTime(model.created_at) },
  ];
  if (canPromote) {
    columns.push({
      key: "release",
      header: "",
      align: "end",
      render: (model) => (model.status === "shadow" ? <RequestRelease model={model} /> : null),
    });
  }
  return (
    <Card title={t.versionsTitle} flush>
      {versions.isPending ? (
        <Skeleton rows={3} label={ru.common.loading} />
      ) : versions.isError ? (
        <StateMessage tone="error" title={ru.errors.loadFailed} description={errorMessage(versions.error)} />
      ) : versions.data.length === 0 ? (
        <StateMessage title={t.versionsEmpty} />
      ) : (
        <Table
          caption={t.versionsTitle}
          columns={columns}
          rows={versions.data}
          rowKey={(model) => model.model_version_id}
        />
      )}
    </Card>
  );
}
