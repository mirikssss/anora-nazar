// Список ролей для входа: название, кто это и кнопка «Войти»; текущая роль — «Продолжить».
import { useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { IconForward } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import { isCurrent, type RoleOption } from "./roleOptions";
import styles from "./RoleOptionList.module.css";
import { useChooseRole } from "./useChooseRole";

interface RoleOptionListProps {
  options: readonly RoleOption[];
  stayOn?: string;
}

export function RoleOptionList({ options, stayOn }: RoleOptionListProps) {
  const session = useSession();
  const choose = useChooseRole(stayOn);
  const pendingKey = choose.isPending ? choose.variables : undefined;
  return (
    <div className={styles.wrap}>
      <ul className={styles.list}>
        {options.map((option) => {
          const current = isCurrent(option, session.identity);
          return (
            <li key={option.key} className={styles.item}>
              <div className={styles.text}>
                <p className={styles.title}>{option.label}</p>
                <p className={styles.description}>{option.description}</p>
              </div>
              <Button
                size="sm"
                variant={current ? "primary" : "secondary"}
                icon={IconForward}
                pending={pendingKey === option.choice}
                disabled={choose.isPending}
                onClick={() => {
                  choose.mutate(option.choice);
                }}
              >
                {current ? ru.entry.continue : ru.entry.enter}
              </Button>
            </li>
          );
        })}
      </ul>
      {choose.isError ? <InlineError message={errorMessage(choose.error)} /> : null}
    </div>
  );
}
