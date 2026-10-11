// Действие заёмщика над заявкой: ответ бэка — новый экран, кладём его в кэш сразу и обновляем списки.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { borrowerKeys, type BorrowerApplication } from "./api";

export function useBorrowerAction<V>(action: (variables: V) => Promise<BorrowerApplication>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: async (application) => {
      queryClient.setQueryData(borrowerKeys.one(application.application_id), application);
      await queryClient.invalidateQueries({ queryKey: borrowerKeys.applications, refetchType: "active" });
    },
  });
}
