// Обучение моделей в контуре: запуск и прогоны со статусом. Пока прогон идёт, список опрашивается;
// когда он завершился — перечитываются версии и отчёт качества.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { isTrainingFinished, modelKeys, useTrainingRuns, type TrainingRun } from "@/entities/model";
import { useStaffName } from "@/entities/risk";
import { hasPermission, useSession } from "@/entities/session";
import { RequestTraining } from "@/features/risk-training";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatNumber } from "@/shared/lib/format";
import { Badge, type BadgeTone } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./TrainingRuns.module.css";

const t = ru.risk.training;

const STATUS_TONES: Readonly<Record<TrainingRun["status"], BadgeTone>> = {
  queued: "neutral",
  running: "blue",
  done: "green",
  failed: "red",
};

function useRefreshWhenFinished(running: boolean) {
  const queryClient = useQueryClient();
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) {
      void queryClient.invalidateQueries({ queryKey: modelKeys.versions });
      void queryClient.invalidateQueries({ queryKey: modelKeys.report });
    }
    wasRunning.current = running;
  }, [running, queryClient]);
}

export function TrainingRuns() {
  const session = useSession();
  const runs = useTrainingRuns();
  const staffName = useStaffName();
  const running = runs.data?.some((run) => !isTrainingFinished(run)) ?? false;
  useRefreshWhenFinished(running);

  const columns: Column<TrainingRun>[] = [
    {
      key: "status",
      header: t.status,
      primary: true,
      render: (run) => (
        <span className={styles.status}>
          <Badge tone={STATUS_TONES[run.status]} dot>
            {label(t.statuses, run.status)}
          </Badge>
          {run.error !== null ? <span className={styles.error}>{run.error}</span> : null}
        </span>
      ),
    },
    { key: "by", header: t.requestedBy, render: (run) => staffName(run.requested_by) },
    { key: "at", header: t.requestedAt, align: "end", render: (run) => formatDateTime(run.requested_at) },
    {
      key: "finished",
      header: t.finishedAt,
      align: "end",
      render: (run) => (run.finished_at === null ? ru.common.none : formatDateTime(run.finished_at)),
    },
    { key: "versions", header: t.versions, align: "end", render: (run) => formatNumber(run.versions.length) },
  ];

  return (
    <Card
      title={t.title}
      subtitle={t.subtitle}
      actions={
        hasPermission(session, PERMISSIONS.promoteModels) ? <RequestTraining running={running} /> : undefined
      }
      flush
    >
      {runs.isPending ? (
        <Skeleton rows={2} label={ru.common.loading} />
      ) : runs.isError ? (
        <StateMessage tone="error" title={ru.errors.loadFailed} description={errorMessage(runs.error)} />
      ) : runs.data.length === 0 ? (
        <StateMessage title={t.empty} />
      ) : (
        <Table caption={t.title} columns={columns} rows={runs.data} rowKey={(run) => run.run_id} />
      )}
    </Card>
  );
}
