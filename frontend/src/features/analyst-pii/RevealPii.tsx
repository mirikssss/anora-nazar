// Полные ПДн заёмщика: только у роли с правом pii.full.view; каждый просмотр бэк пишет в журнал.
import { hasPermission, useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./RevealPii.module.css";

const t = ru.analyst;

interface RevealPiiProps {
  revealed: boolean;
  pending: boolean;
  error: unknown;
  onReveal: () => void;
}

export function RevealPii({ revealed, pending, error, onReveal }: RevealPiiProps) {
  const session = useSession();
  if (!hasPermission(session, PERMISSIONS.viewFullPii)) return null;
  return (
    <div className={styles.reveal}>
      {revealed && !pending && error === null ? (
        <p className={styles.hint}>{t.fullPiiShown}</p>
      ) : (
        <>
          <Button size="sm" pending={pending} onClick={onReveal}>
            {t.showFullPii}
          </Button>
          <p className={styles.hint}>{t.fullPiiHint}</p>
        </>
      )}
      {error !== null ? <InlineError message={errorMessage(error)} /> : null}
    </div>
  );
}
