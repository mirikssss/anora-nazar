// Сеть кредиторов глазами своего контура: переключатель из политики, правила и счётчики оператора.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type NetworkOverview = NodeSchemas["schemas"]["NetworkOverviewOut"];

export const networkKeys = {
  overview: ["network", "overview"] as const,
};

export function useNetworkOverview() {
  return useQuery({
    queryKey: networkKeys.overview,
    queryFn: () => request(nodeApi.GET("/v1/network/overview")),
  });
}
