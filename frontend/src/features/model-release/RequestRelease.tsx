// Запрос выпуска модели из тени: второй подписант — другой сотрудник (Блок 4).
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { modelKeys, requestRelease, type ModelVersion } from "@/entities/model";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./RequestRelease.module.css";

export function RequestRelease({ model }: { model: ModelVersion }) {
  const queryClient = useQueryClient();
  const release = useMutation({
    mutationFn: () => requestRelease(model.model_version_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: modelKeys.versions }),
  });
  if (release.isSuccess) return <span className={styles.note}>{ru.models.releaseRequested}</span>;
  return (
    <span className={styles.wrap}>
      <Button
        size="sm"
        pending={release.isPending}
        onClick={() => {
          release.mutate();
        }}
      >
        {ru.models.release}
      </Button>
      {release.isError ? <InlineError message={errorMessage(release.error)} /> : null}
    </span>
  );
}
