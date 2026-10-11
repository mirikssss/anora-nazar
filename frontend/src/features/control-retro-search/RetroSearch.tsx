// Ретро-поиск Т6: выданные кредиты с общими идентификаторами заявок дела. Запуск пишется в ленту и журнал.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { caseKeys, retroSearch, type RetroSearch as RetroResult } from "@/entities/case";
import { hasPermission, useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { IconDecision } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./RetroSearch.module.css";

const t = ru.control.retro;

type Match = RetroResult["matches"][number];

const COLUMNS: readonly Column<Match>[] = [
  {
    key: "application",
    header: t.application,
    primary: true,
    render: (match) => <span className="num">{match.application_id}</span>,
  },
  {
    key: "shared",
    header: t.shared,
    render: (match) => match.shared.map((kind) => label(t.kinds, kind)).join(", "),
  },
];

export function RetroSearch({ caseId }: { caseId: string }) {
  const session = useSession();
  const queryClient = useQueryClient();
  const search = useMutation({
    mutationFn: () => retroSearch(caseId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) }),
  });

  if (!hasPermission(session, PERMISSIONS.runRetroSearch)) return <p className={styles.hint}>{t.noRight}</p>;

  return (
    <div className={styles.retro}>
      <div>
        <Button
          icon={IconDecision}
          pending={search.isPending}
          onClick={() => {
            search.mutate();
          }}
        >
          {search.data === undefined ? t.run : t.runAgain}
        </Button>
      </div>
      {search.isError ? <InlineError message={errorMessage(search.error)} /> : null}
      {search.data !== undefined ? (
        search.data.matches.length === 0 ? (
          <p className={styles.hint}>{t.none}</p>
        ) : (
          <>
            <p className={styles.hint}>
              {t.found}: <span className="num">{search.data.matches.length}</span>
            </p>
            <Table
              caption={t.caption}
              columns={COLUMNS}
              rows={search.data.matches}
              rowKey={(match) => match.application_id}
            />
          </>
        )
      ) : null}
    </div>
  );
}
