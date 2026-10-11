// Запуск обучения: прогон идёт фоном на бэке, список прогонов опрашивается, пока он не завершится.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { modelKeys, requestTraining } from "@/entities/model";
import { errorMessage } from "@/shared/api";
import { IconRefresh } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./RequestTraining.module.css";

export function RequestTraining({ running }: { running: boolean }) {
  const queryClient = useQueryClient();
  const training = useMutation({
    mutationFn: requestTraining,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: modelKeys.trainingRuns }),
  });
  return (
    <span className={styles.wrap}>
      <Button
        size="sm"
        icon={IconRefresh}
        pending={training.isPending || running}
        onClick={() => {
          training.mutate();
        }}
      >
        {ru.risk.training.run}
      </Button>
      {training.isError ? <InlineError message={errorMessage(training.error)} /> : null}
    </span>
  );
}
