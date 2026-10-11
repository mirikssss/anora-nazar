// «/bank/core-banking» — АБС: зачисление и оплата поставщику по разрешению узла, акт приёмки (Т5),
// перевод с карты (Т3), кнопки сбоев.
import { useId } from "react";

import type { Operation } from "@/entities/operation";
import type { AcceptanceAct } from "@/entities/program";
import { AcceptanceActPanel } from "@/features/acceptance-act";
import { TransferPanel } from "@/features/bank-transfer";
import { ExecuteOperation } from "@/features/execute-operation";
import { FailurePanel } from "@/features/inject-failure";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Tabs } from "@/shared/ui/Tabs";
import { Operations } from "@/widgets/operations/Operations";

import styles from "./BankPage.module.css";
import { usePageParams } from "./usePageParams";

const TAB = "tab";
const TABS = { operation: "operation", act: "act", transfer: "transfer" } as const;
type TabKey = (typeof TABS)[keyof typeof TABS];
const t = ru.borrower.tabs;

function asTab(value: string | null): TabKey {
  return value === TABS.act || value === TABS.transfer ? value : TABS.operation;
}

export function CoreBankingPage() {
  const params = usePageParams();
  const panelId = useId();
  const tab = asTab(params.get(TAB));
  const applicationId = params.get("application");
  const actId = params.get("act");
  const select = (operation: Operation) => {
    params.patch({ operation: operation.operation_key });
  };
  const pay = (act: AcceptanceAct) => {
    params.patch({ [TAB]: TABS.operation, application: act.application_id, act: act.act_id });
  };
  return (
    <>
      <PageHeader
        title={ru.coreBanking.title}
        subtitle={ru.coreBanking.subtitle}
        tag={<Badge tone="outline">{ru.common.simulator}</Badge>}
      />
      <div className={styles.columns}>
        <div className={styles.stack}>
          <Tabs
            label={t.label}
            panelId={panelId}
            selected={tab}
            items={[
              { key: TABS.operation, label: t.operation },
              { key: TABS.act, label: t.act },
              { key: TABS.transfer, label: t.transfer },
            ]}
            onSelect={(key) => {
              params.patch({ [TAB]: key });
            }}
          />
          <div id={panelId} role="tabpanel">
            {tab === TABS.operation ? (
              // Оплата по акту приходит адресом: форма открывается заново на этой заявке и акте.
              <ExecuteOperation
                key={`${applicationId ?? ""}:${actId ?? ""}`}
                initialApplicationId={applicationId}
                initialActId={actId}
                onExecuted={select}
              />
            ) : tab === TABS.act ? (
              <AcceptanceActPanel initialApplicationId={applicationId} onPay={pay} />
            ) : (
              <TransferPanel initialApplicationId={applicationId} />
            )}
          </div>
        </div>
        <div className={styles.stack}>
          <Operations selectedKey={params.get("operation")} onSelect={select} />
          <FailurePanel />
        </div>
      </div>
    </>
  );
}
