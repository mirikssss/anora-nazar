// Версии моделей: типы и запросы.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type ModelVersion = NodeSchemas["schemas"]["ModelVersionOut"];

export function useModelVersions(enabled: boolean) {
  return useQuery({
    queryKey: ["models"] as const,
    queryFn: () => request(nodeApi.GET("/v1/models")),
    enabled,
  });
}
