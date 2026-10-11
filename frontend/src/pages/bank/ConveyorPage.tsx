// «/bank/conveyor» — новая заявка: канал, свой ввод; ответ узла рядом. Сценарии в один клик — Ф3.
import { useSearchParams } from "react-router";

import { useApplications, type Application } from "@/entities/application";
import { ApplicationForm } from "@/features/submit-application";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { ApplicationDetail } from "@/widgets/application-detail/ApplicationDetail";
import { ApplicationList } from "@/widgets/application-list/ApplicationList";

import styles from "./BankPage.module.css";

const SELECTED = "application";

export function ConveyorPage() {
  const [params, setParams] = useSearchParams();
  const selectedId = params.get(SELECTED);
  const applications = useApplications();
  const selected = applications.data?.find((app) => app.id === selectedId) ?? null;
  const select = (application: Application) => {
    setParams({ [SELECTED]: application.id }, { replace: true });
  };

  return (
    <>
      <PageHeader
        title={ru.conveyor.title}
        subtitle={ru.conveyor.subtitle}
        tag={<Badge tone="outline">{ru.common.simulator}</Badge>}
      />
      <div className={styles.columns}>
        <ApplicationForm onSubmitted={select} />
        <div className={styles.stack}>
          <ApplicationList selectedId={selectedId} onSelect={select} />
          <ApplicationDetail application={selected} />
        </div>
      </div>
    </>
  );
}
