// Пульт симулятора рядом с телефоном: заявки сценариев, запущенных в конвейере, — открыть их в приложении.
import { useBorrowerApplications } from "@/entities/borrower";
import { useClientTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatSum, formatTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import styles from "./ScenarioApplications.module.css";

const t = ru.borrower.simulator;

interface ScenarioApplicationsProps {
  selectedId: string | null;
  onOpen: (applicationId: string) => void;
}

export function ScenarioApplications({ selectedId, onOpen }: ScenarioApplicationsProps) {
  const applications = useBorrowerApplications(null);
  const screens = useClientTexts().data?.client_screens;
  // Заявки персон подаются из самого приложения; без персоны — пришли из сценариев конвейера.
  const fromScenarios = (applications.data ?? []).filter((application) => application.persona_code === null);
  return (
    <Card title={t.title} subtitle={t.hint} actions={<Badge tone="outline">{ru.common.simulator}</Badge>}>
      {applications.isPending ? (
        <Skeleton rows={3} label={ru.borrower.applicationsLoading} />
      ) : applications.isError ? (
        <InlineError message={errorMessage(applications.error)} />
      ) : fromScenarios.length === 0 ? (
        <StateMessage title={t.empty} description={t.emptyHint} />
      ) : (
        <ul className={styles.list}>
          {fromScenarios.map((application) => {
            const selected = application.application_id === selectedId;
            return (
              <li key={application.application_id}>
                <button
                  type="button"
                  className={[styles.item, selected ? styles.selected : ""].join(" ")}
                  aria-current={selected || undefined}
                  onClick={() => {
                    onOpen(application.application_id);
                  }}
                >
                  <span className={styles.main}>
                    <code>{application.application_id}</code>
                    <span className="num">{formatSum(application.loan.amount)}</span>
                  </span>
                  <span className={styles.meta}>
                    {screens?.[application.screen]?.title ?? application.screen} ·{" "}
                    {formatTime(application.created_at)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
