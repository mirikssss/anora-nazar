// «Взять в работу»: дело закрепляется за аналитиком, запись уходит в ленту и в журнал.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { assignCase, caseKeys } from "@/entities/case";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

export function AssignCaseButton({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const assign = useMutation({
    mutationFn: () => assignCase(caseId),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) }),
        queryClient.invalidateQueries({ queryKey: caseKeys.queues }),
      ]),
  });
  return (
    <>
      <Button
        variant="primary"
        wide
        pending={assign.isPending}
        onClick={() => {
          assign.mutate();
        }}
      >
        {ru.analyst.assign}
      </Button>
      {assign.isError ? <InlineError message={errorMessage(assign.error)} /> : null}
    </>
  );
}
