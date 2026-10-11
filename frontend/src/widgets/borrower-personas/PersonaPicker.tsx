// Вход в приложение банка от имени синтетического клиента: имя, возраст, кто он и сколько на карте.
import { AppScreen, usePersonas } from "@/entities/borrower";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatSum } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import styles from "./PersonaPicker.module.css";

const t = ru.borrower;

export function PersonaPicker({ onSelect }: { onSelect: (personaCode: string) => void }) {
  const personas = usePersonas();
  return (
    <AppScreen title={t.personasTitle} lead={t.personasHint}>
      {personas.isPending ? (
        <Skeleton rows={5} label={t.personasLoading} />
      ) : personas.isError ? (
        <StateMessage
          tone="error"
          title={ru.errors.loadFailed}
          description={errorMessage(personas.error)}
          action={
            <Button
              onClick={() => {
                void personas.refetch();
              }}
            >
              {ru.common.retry}
            </Button>
          }
        />
      ) : personas.data.length === 0 ? (
        <StateMessage title={t.personasEmpty} />
      ) : (
        <ul className={styles.list}>
          {personas.data.map((persona) => (
            <li key={persona.code}>
              <button
                type="button"
                className={styles.persona}
                onClick={() => {
                  onSelect(persona.code);
                }}
              >
                <span className={styles.head}>
                  <span className={styles.name}>{persona.display_name}</span>
                  <span className={styles.meta}>
                    {t.age} {persona.age}
                  </span>
                </span>
                <span className={styles.summary}>{persona.summary}</span>
                <span className={styles.meta}>
                  {t.balance} <span className="num">{formatSum(persona.card_balance)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </AppScreen>
  );
}
