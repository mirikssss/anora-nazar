// Филиалы и сотрудники банка-пилота — справочник имитатора.
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";

export type Branch = BankSchemas["schemas"]["BranchOut"];

export function useBranches() {
  return useQuery({
    queryKey: ["branches"] as const,
    queryFn: () => request(bankApi.GET("/v1/staff/branches")),
    staleTime: Infinity,
  });
}
