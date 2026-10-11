// Переводы с карты после зачисления (Т3): рекомендация узла и решение транзакционного антифрода банка.
import { useQuery } from "@tanstack/react-query";

import { parseResult, type DecisionResult } from "@/entities/decision";
import { bankApi, request, type BankSchemas } from "@/shared/api";
import { str } from "@/shared/lib/json";

export type Transfer = BankSchemas["schemas"]["TransferOut"];
export type TransferRequest = BankSchemas["schemas"]["TransferIn"];
export type TransferAction = BankSchemas["schemas"]["TransferDecisionIn"]["action"];

export const HELD_STATUS = "held";

export const transferKeys = {
  all: ["transfers"] as const,
  byApplication: (applicationId: string) => ["transfers", applicationId] as const,
};

export function useTransfers(applicationId: string) {
  return useQuery({
    queryKey: transferKeys.byApplication(applicationId),
    queryFn: () =>
      request(bankApi.GET("/v1/transfers", { params: { query: { application_id: applicationId } } })),
    enabled: applicationId !== "",
  });
}

export function createTransfer(body: TransferRequest): Promise<Transfer> {
  return request(bankApi.POST("/v1/transfers", { body }));
}

export function decideTransfer(transferId: string, action: TransferAction): Promise<Transfer> {
  return request(
    bankApi.POST("/v1/transfers/{transfer_id}/decision", {
      params: { path: { transfer_id: transferId } },
      body: { action },
    }),
  );
}

export interface Recommendation extends DecisionResult {
  recommendedAction: string | null;
}

/** Рекомендация узла хранится как JSON ответа Т3: уровень, действие и причины. */
export function recommendation(transfer: Transfer): Recommendation | null {
  const raw = transfer.recommendation;
  if (raw === null) return null;
  return { ...parseResult(raw), recommendedAction: str(raw.recommended_action) };
}

/** Своё правило ТАФ, если узел не ответил: задержать или пропустить. */
export function ownRuleHold(transfer: Transfer): boolean | null {
  const hold = transfer.own_rule?.hold;
  return typeof hold === "boolean" ? hold : null;
}

export function nodeErrorMessage(transfer: Transfer): string | null {
  return transfer.node_error === null
    ? null
    : (str(transfer.node_error.message) ?? str(transfer.node_error.code));
}
