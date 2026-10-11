// «/bank/conveyor» — новая заявка: готовые сценарии в один клик или свой ввод; ответ узла рядом.
import { useId } from "react";

import { useApplications, type Application } from "@/entities/application";
import { ScenarioPicker } from "@/features/run-scenario";
import { ApplicationForm } from "@/features/submit-application";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Tabs } from "@/shared/ui/Tabs";
import { ApplicationDetail } from "@/widgets/application-detail/ApplicationDetail";
import { ApplicationList } from "@/widgets/application-list/ApplicationList";

import styles from "./BankPage.module.css";
import { usePageParams } from "./usePageParams";

const SELECTED = "application";
const TAB = "input";
const TABS = { scenarios: "scenarios", own: "own" } as const;
const t = ru.borrower.scenarios;

export function ConveyorPage() {
  const params = usePageParams();
  const panelId = useId();
  const selectedId = params.get(SELECTED);
  const tab = params.get(TAB) === TABS.own ? TABS.own : TABS.scenarios;
  const applications = useApplications();
  const selected = applications.data?.find((app) => app.id === selectedId) ?? null;
  const selectId = (applicationId: string) => {
    params.patch({ [SELECTED]: applicationId });
  };
  const select = (application: Application) => {
    selectId(application.id);
  };

  return (
    <>
      <PageHeader
        title={ru.conveyor.title}
        subtitle={ru.conveyor.subtitle}
        tag={<Badge tone="outline">{ru.common.simulator}</Badge>}
      />
      <div className={styles.columns}>
        <div className={styles.stack}>
          <Tabs
            label={t.tabsLabel}
            panelId={panelId}
            selected={tab}
            items={[
              { key: TABS.scenarios, label: t.tabScenarios },
              { key: TABS.own, label: t.tabOwn },
            ]}
            onSelect={(key) => {
              params.patch({ [TAB]: key });
            }}
          />
          <div id={panelId} role="tabpanel">
            {tab === TABS.scenarios ? (
              <ScenarioPicker onOpenApplication={selectId} />
            ) : (
              <ApplicationForm onSubmitted={select} />
            )}
          </div>
        </div>
        <div className={styles.stack}>
          <ApplicationList selectedId={selectedId} onSelect={select} />
          <ApplicationDetail application={selected} />
        </div>
      </div>
    </>
  );
}
