// «/risk/audit» — журнал и проверка целостности.
import { AuditVerify } from "@/features/audit-verify";
import { ru } from "@/shared/i18n/ru";
import { PageHeader } from "@/shared/ui/PageHeader";
import { AuditChain } from "@/widgets/audit-chain/AuditChain";

import styles from "./AuditPage.module.css";

export function AuditPage() {
  return (
    <>
      <PageHeader title={ru.audit.title} subtitle={ru.audit.subtitle} />
      <div className={styles.columns}>
        <AuditVerify />
        <AuditChain />
      </div>
    </>
  );
}
