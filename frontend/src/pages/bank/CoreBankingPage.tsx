// «/bank/core-banking» — АБС: исполнение по разрешению узла, кнопки сбоев.
import { useSearchParams } from "react-router";

import type { Operation } from "@/entities/operation";
import { ExecuteOperation } from "@/features/execute-operation";
import { FailurePanel } from "@/features/inject-failure";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Operations } from "@/widgets/operations/Operations";

import styles from "./BankPage.module.css";

export function CoreBankingPage() {
  const [params, setParams] = useSearchParams();
  const select = (operation: Operation) => {
    setParams({ operation: operation.operation_key }, { replace: true });
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
          <ExecuteOperation initialApplicationId={params.get("application")} onExecuted={select} />
          <FailurePanel />
        </div>
        <div className={styles.stack}>
          <Operations selectedKey={params.get("operation")} onSelect={select} />
        </div>
      </div>
    </>
  );
}
