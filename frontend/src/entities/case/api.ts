// Дела антифрод-центра и внутреннего контроля: очереди, дело, граф, действия по заявкам, исход, ретро-поиск.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

type S = NodeSchemas["schemas"];
export type CaseQueue = "online" | "group";
export type CaseListItem = S["CaseListItem"];
export type CaseDetail = S["CaseDetailOut"];
export type CaseApplication = S["CaseApplicationOut"];
export type CaseGraph = S["CaseGraphOut"];
export type GraphNode = S["GraphNodeOut"];
export type GraphEdge = S["GraphEdgeOut"];
export type ParticipantDecision = S["ParticipantDecisionIn"];
export type CaseOutcome = S["node__modules__cases__schemas__OutcomeIn"];
export type RetroSearch = S["RetroSearchOut"];
export type VerificationQuestions = S["QuestionsOut"];

export const caseKeys = {
  queues: ["cases"] as const,
  queue: (queue: CaseQueue) => ["cases", queue] as const,
  detail: (caseId: string) => ["case", caseId] as const,
  graph: (caseId: string) => ["case", caseId, "graph"] as const,
  questions: ["verification-questions"] as const,
};

export function useCaseQueue(queue: CaseQueue) {
  return useQuery({
    queryKey: caseKeys.queue(queue),
    queryFn: () => request(nodeApi.GET("/v1/cases", { params: { query: { queue } } })),
  });
}

export function useCase(caseId: string, fullPii = false) {
  return useQuery({
    queryKey: [...caseKeys.detail(caseId), fullPii] as const,
    queryFn: () =>
      request(
        nodeApi.GET("/v1/cases/{case_id}", {
          params: { path: { case_id: caseId }, query: { full_pii: fullPii } },
        }),
      ),
  });
}

export function useCaseGraph(caseId: string) {
  return useQuery({
    queryKey: caseKeys.graph(caseId),
    queryFn: () =>
      request(nodeApi.GET("/v1/cases/{case_id}/graph", { params: { path: { case_id: caseId } } })),
  });
}

export function useVerificationQuestions() {
  return useQuery({
    queryKey: caseKeys.questions,
    queryFn: () => request(nodeApi.GET("/v1/verification/questions")),
    staleTime: Infinity,
  });
}

export function assignCase(caseId: string): Promise<CaseListItem> {
  return request(nodeApi.POST("/v1/cases/{case_id}/assignment", { params: { path: { case_id: caseId } } }));
}

export function decideApplication(caseId: string, applicationId: string, body: ParticipantDecision) {
  return request(
    nodeApi.POST("/v1/cases/{case_id}/applications/{application_id}/decision", {
      params: { path: { case_id: caseId, application_id: applicationId } },
      body,
    }),
  );
}

export function recordOutcome(caseId: string, body: CaseOutcome) {
  return request(
    nodeApi.POST("/v1/cases/{case_id}/outcome", { params: { path: { case_id: caseId } }, body }),
  );
}

export function retroSearch(caseId: string): Promise<RetroSearch> {
  return request(nodeApi.POST("/v1/cases/{case_id}/retro-search", { params: { path: { case_id: caseId } } }));
}
