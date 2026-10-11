// Запросы решения: запись, повтор, сравнение версий.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request } from "@/shared/api";

import type { Comparison, Replay } from "./model";

export const decisionKeys = {
  record: (decisionId: string) => ["decision", decisionId] as const,
};

export function useDecisionRecord(decisionId: string) {
  return useQuery({
    queryKey: decisionKeys.record(decisionId),
    queryFn: () =>
      request(nodeApi.GET("/v1/decisions/{decision_id}", { params: { path: { decision_id: decisionId } } })),
    // Запись решения неизменяема.
    staleTime: Infinity,
  });
}

export function replayDecision(decisionId: string): Promise<Replay> {
  return request(
    nodeApi.GET("/v1/decisions/{decision_id}/replay", { params: { path: { decision_id: decisionId } } }),
  );
}

export function compareDecision(decisionId: string, modelVersionIds: string[]): Promise<Comparison> {
  return request(
    nodeApi.POST("/v1/decisions/{decision_id}/comparison", {
      params: { path: { decision_id: decisionId } },
      body: { model_version_ids: modelVersionIds },
    }),
  );
}
