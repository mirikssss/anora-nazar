// Подача своей заявки: самозапрет в реестр и события сессии — до заявки, как в банке; затем конвейер.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { applicationKeys, submitApplication, type Application } from "@/entities/application";

import { recordSessionEvent, setSelfBan } from "./api";
import { toDraft, type FormState } from "./form";

async function submit(state: FormState): Promise<Application> {
  const pinfl = state.pinfl.trim();
  if (state.selfBan !== "none") await setSelfBan(pinfl, state.selfBan);
  const deviceId = state.deviceId.trim() === "" ? null : state.deviceId.trim();
  const sessionRefs: string[] = [];
  for (const eventType of state.sessionEvents) {
    sessionRefs.push(await recordSessionEvent(pinfl, eventType, deviceId));
  }
  return submitApplication(toDraft(state, sessionRefs));
}

export function useSubmitApplication(onSubmitted: (application: Application) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: submit,
    onSuccess: (application) => {
      onSubmitted(application);
    },
    // Узел мог не ответить, а заявка уже создана и ждёт: список обновляем в любом случае.
    onSettled: () => queryClient.invalidateQueries({ queryKey: applicationKeys.all }),
  });
}
