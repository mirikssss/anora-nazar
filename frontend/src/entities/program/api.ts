// Платформа программ в имитаторе банка: справочник помощников хокима и акты приёмки (Т5).
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";

export type Helper = BankSchemas["schemas"]["HelperOut"];
export type Supplier = BankSchemas["schemas"]["SupplierOut"];
export type AcceptanceAct = BankSchemas["schemas"]["ActOut"];
export type AcceptanceActRequest = BankSchemas["schemas"]["ActIn"];
export type SignerRole = AcceptanceActRequest["signer_role"];

export const SIGNER_ROLES: readonly SignerRole[] = ["helper", "mahalla_banker", "veterinary"];

export const programKeys = {
  helpers: (district: string | null) => ["program", "helpers", district] as const,
  suppliers: (district: string | null, category: string | null) =>
    ["program", "suppliers", district, category] as const,
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

/** Поставщики района по категории товара; без района или категории — без фильтра по ним. */
export function useSuppliers(district: string | null, category: string | null) {
  return useQuery({
    queryKey: programKeys.suppliers(district, category),
    queryFn: () =>
      request(
        bankApi.GET("/v1/program/suppliers", {
          params: {
            query: {
              ...(district === null ? {} : { district }),
              ...(category === null ? {} : { category }),
            },
          },
        }),
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
