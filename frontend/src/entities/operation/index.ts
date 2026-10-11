// Операции АБС по ключу бизнес-операции и кнопки сбоев симулятора.
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";

export type Operation = BankSchemas["schemas"]["OperationOut"];
export type OperationRequest = BankSchemas["schemas"]["OperationIn"];
export type OperationType = OperationRequest["operation_type"];
export type FailureFlags = BankSchemas["schemas"]["Flags"];
export type RepeatResult = BankSchemas["schemas"]["RepeatOut"];

export const operationKeys = {
  all: ["operations"] as const,
  failures: ["failures"] as const,
};

export function useOperations() {
  return useQuery({
    queryKey: operationKeys.all,
    queryFn: () => request(bankApi.GET("/v1/core-banking/operations")),
  });
}

export function executeOperation(body: OperationRequest): Promise<Operation> {
  return request(bankApi.POST("/v1/core-banking/operations", { body }));
}

export function useFailureFlags() {
  return useQuery({
    queryKey: operationKeys.failures,
    queryFn: () => request(bankApi.GET("/v1/failures")),
  });
}

export function setFailureFlags(patch: Partial<FailureFlags>): Promise<FailureFlags> {
  return request(bankApi.PATCH("/v1/failures", { body: patch }));
}

export function repeatWithOtherAmount(operationKey: string, amount: number): Promise<RepeatResult> {
  return request(
    bankApi.POST("/v1/failures/repeat-with-other-amount", { body: { operation_key: operationKey, amount } }),
  );
}
