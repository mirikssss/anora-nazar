// Приложение заёмщика в имитаторе банка: персоны, заявки и экран по каждой, действия клиента.
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";

export type Persona = BankSchemas["schemas"]["PersonaOut"];
export type BorrowerApplication = BankSchemas["schemas"]["BorrowerScreenOut"];
export type BorrowerScreen = BorrowerApplication["screen"];
export type BorrowerDraft = BankSchemas["schemas"]["BorrowerApplicationIn"];
export type IntentAnswer = BankSchemas["schemas"]["IntentAnswer"];

/** Экраны, которые меняются без действий заёмщика: аналитик снимает паузу, узел принимает ответы. */
const WAITING_SCREENS: readonly BorrowerScreen[] = ["under_review", "pause"];
// Частота опроса — удобство интерфейса одного зрителя, не параметр продукта.
const POLL_INTERVAL_MS = 3000;

export const borrowerKeys = {
  personas: ["borrower", "personas"] as const,
  applications: ["borrower", "applications"] as const,
  list: (personaCode: string | null) => ["borrower", "applications", "list", personaCode] as const,
  one: (applicationId: string) => ["borrower", "applications", "one", applicationId] as const,
};

export function usePersonas() {
  return useQuery({
    queryKey: borrowerKeys.personas,
    queryFn: () => request(bankApi.GET("/v1/borrower/personas")),
    staleTime: Infinity,
  });
}

/** Заявки персоны; без персоны — все заявки, видимые в приложении (в том числе из сценариев). */
export function useBorrowerApplications(personaCode: string | null) {
  return useQuery({
    queryKey: borrowerKeys.list(personaCode),
    queryFn: () =>
      request(
        bankApi.GET("/v1/borrower/applications", {
          params: { query: personaCode === null ? {} : { persona_code: personaCode } },
        }),
      ),
  });
}

export function useBorrowerApplication(applicationId: string) {
  return useQuery({
    queryKey: borrowerKeys.one(applicationId),
    queryFn: () =>
      request(
        bankApi.GET("/v1/borrower/applications/{application_id}", {
          params: { path: { application_id: applicationId } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.data !== undefined && WAITING_SCREENS.includes(query.state.data.screen)
        ? POLL_INTERVAL_MS
        : false,
  });
}

export function submitBorrowerApplication(draft: BorrowerDraft): Promise<BorrowerApplication> {
  return request(bankApi.POST("/v1/borrower/applications", { body: draft }));
}

const path = (applicationId: string) => ({ params: { path: { application_id: applicationId } } });

export function answerIntent(applicationId: string, answers: IntentAnswer[]): Promise<BorrowerApplication> {
  return request(
    bankApi.POST("/v1/borrower/applications/{application_id}/intent-answers", {
      ...path(applicationId),
      body: { answers },
    }),
  );
}

export function reportPressure(applicationId: string): Promise<BorrowerApplication> {
  return request(bankApi.POST("/v1/borrower/applications/{application_id}/pressure", path(applicationId)));
}

export function cancelBorrowerApplication(applicationId: string): Promise<BorrowerApplication> {
  return request(bankApi.POST("/v1/borrower/applications/{application_id}/cancel", path(applicationId)));
}
