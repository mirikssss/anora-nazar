// «/» — вход в проект: что это и выбор роли.
import { useBankRoles, useSession, useStaffRoles } from "@/entities/session";
import { bankOptions, RoleOptionList, staffOptions, type RoleOption } from "@/features/role-switch";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import styles from "./EntryPage.module.css";

interface RoleGroupProps {
  title: string;
  query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  options: readonly RoleOption[];
}

function RoleGroup({ title, query, options }: RoleGroupProps) {
  return (
    <Card title={title}>
      {query.isPending ? (
        <Skeleton rows={3} label={ru.entry.rolesLoading} />
      ) : query.isError ? (
        <StateMessage
          tone="error"
          title={ru.entry.rolesFailed}
          description={errorMessage(query.error)}
          action={
            <Button size="sm" onClick={() => void query.refetch()}>
              {ru.common.retry}
            </Button>
          }
        />
      ) : (
        <RoleOptionList options={options} />
      )}
    </Card>
  );
}

export function EntryPage() {
  const session = useSession();
  const bankRoles = useBankRoles();
  const staffRoles = useStaffRoles();
  return (
    <div className={styles.page}>
      <section className={styles.about}>
        <h1 className={styles.title}>{ru.entry.title}</h1>
        <p className={styles.lead}>{ru.entry.lead}</p>
        {ru.entry.about.map((paragraph) => (
          <p key={paragraph} className={styles.paragraph}>
            {paragraph}
          </p>
        ))}
        <p className={styles.note}>{ru.entry.demoNote}</p>
      </section>
      <section className={styles.roles} aria-labelledby="choose-role">
        <h2 id="choose-role" className={styles.rolesTitle}>
          {ru.entry.chooseRole}
        </h2>
        {session.expired ? <StateMessage tone="error" title={ru.errors.expired} /> : null}
        <RoleGroup title={ru.roleGroups.bank} query={bankRoles} options={bankOptions(bankRoles.data ?? [])} />
        <RoleGroup
          title={ru.roleGroups.product}
          query={staffRoles}
          options={staffOptions(staffRoles.data ?? [])}
        />
      </section>
    </div>
  );
}
