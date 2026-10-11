// Платформа программ в имитаторе банка: справочник помощников хокима и акты приёмки (Т5).
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";

export type Helper = BankSchemas["schemas"]["HelperOut"];
export type AcceptanceAct = BankSchemas["schemas"]["ActOut"];
export type AcceptanceActRequest = BankSchemas["schemas"]["ActIn"];
export type SignerRole = AcceptanceActRequest["signer_role"];

export const SIGNER_ROLES: readonly SignerRole[] = ["helper", "mahalla_banker", "veterinary"];

export const programKeys = {
  helpers: (district: string | null) => ["program", "helpers", district] as const,
  acts: (applicationId: string) => ["program", "acts", applicationId] as const,
};

export function useHelpers(district: string | null) {
  return useQuery({
    queryKey: programKeys.helpers(district),
    queryFn: () =>
      request(
        bankApi.GET("/v1/program/helpers", { params: { query: district === null ? {} : { district } } }),
      ),
    staleTime: Infinity,
  });
}

export function useActs(applicationId: string) {
  return useQuery({
    queryKey: programKeys.acts(applicationId),
    queryFn: () =>
      request(bankApi.GET("/v1/program/acts", { params: { query: { application_id: applicationId } } })),
    enabled: applicationId !== "",
  });
}

export function createAct(body: AcceptanceActRequest): Promise<AcceptanceAct> {
  return request(bankApi.POST("/v1/program/acts", { body }));
}
