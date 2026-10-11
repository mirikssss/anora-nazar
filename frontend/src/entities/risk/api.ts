// Обзор риск-менеджера: уровни по дням, очереди дел, дрейф признаков.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type RiskOverview = NodeSchemas["schemas"]["RiskOverviewOut"];
export type DayLevels = NodeSchemas["schemas"]["DayLevels"];
export type Drift = NodeSchemas["schemas"]["DriftOut"];

export const riskKeys = {
  overview: ["risk", "overview"] as const,
};

export function useRiskOverview() {
  return useQuery({
    queryKey: riskKeys.overview,
    queryFn: () => request(nodeApi.GET("/v1/risk/overview")),
  });
}
