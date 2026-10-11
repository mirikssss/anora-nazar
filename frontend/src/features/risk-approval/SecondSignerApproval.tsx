// Подтверждение вторым подписантом (Блок 4): порог политики или выпуск модели. Кто начал действие,
// тот его не подтверждает — кнопка неактивна с пояснением; окончательно это проверяет бэк.
import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { isOwnRequest } from "@/entities/risk";
import { useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./SecondSignerApproval.module.css";

interface SecondSignerApprovalProps {
  requestedBy: string;
  approve: () => Promise<unknown>;
  /** Что перечитать после подтверждения: список ожидающих и то, что изменилось. */
  invalidate: readonly QueryKey[];
  /** В конце строки таблицы — по правому краю; в блоке текста — по левому. */
  align?: "start" | "end";
}

export function SecondSignerApproval({
  requestedBy,
  approve,
  invalidate,
  align = "end",
}: SecondSignerApprovalProps) {
  const session = useSession();
  const queryClient = useQueryClient();
  const approval = useMutation({
    mutationFn: approve,
    onSuccess: () => Promise.all(invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
  const own = isOwnRequest(session, requestedBy);
  return (
    <span className={[styles.wrap, align === "start" ? styles.start : ""].join(" ")}>
      <Button
        size="sm"
        variant="primary"
        disabled={own}
        pending={approval.isPending}
        title={own ? ru.risk.secondSigner : undefined}
        onClick={() => {
          approval.mutate();
        }}
      >
        {ru.risk.approve}
      </Button>
      {own ? <span className={styles.note}>{ru.risk.secondSigner}</span> : null}
      {approval.isError ? <InlineError message={errorMessage(approval.error)} /> : null}
    </span>
  );
}
