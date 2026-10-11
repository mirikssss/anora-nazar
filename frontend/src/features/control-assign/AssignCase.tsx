// «Взять в работу»: дело закрепляется за сотрудником, запись — в ленте и журнале.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { assignCase, caseKeys, type CaseDetail } from "@/entities/case";
import { hasPermission, useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { IconCheck } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

export function AssignCase({ detail }: { detail: CaseDetail }) {
  const session = useSession();
  const queryClient = useQueryClient();
  const assign = useMutation({
    mutationFn: () => assignCase(detail.case_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: caseKeys.detail(detail.case_id) }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: caseKeys.queues }),
  });
  const userCode = session.identity?.kind === "staff" ? session.identity.userCode : null;
  const available =
    hasPermission(session, PERMISSIONS.decideGroupCases) &&
    detail.status !== "closed" &&
    detail.assignee !== userCode;
  if (!available) return null;
  return (
    <>
      <Button
        variant="primary"
        icon={IconCheck}
        pending={assign.isPending}
        onClick={() => {
          assign.mutate();
        }}
      >
        {ru.control.take}
      </Button>
      {assign.isError ? <InlineError message={errorMessage(assign.error)} /> : null}
    </>
  );
}
