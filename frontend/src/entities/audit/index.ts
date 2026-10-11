// Журнал контура: записи, контрольные точки, проверка целостности.
import { useInfiniteQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type AuditRecord = NodeSchemas["schemas"]["RecordOut"];
export type Verification = NodeSchemas["schemas"]["VerificationOut"];
export type Checkpoint = NodeSchemas["schemas"]["CheckpointOut"];

const PAGE_SIZE = 50;

export const auditKeys = {
  records: ["audit", "records"] as const,
};

export function useAuditRecords() {
  return useInfiniteQuery({
    queryKey: auditKeys.records,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      request(
        nodeApi.GET("/v1/audit/records", { params: { query: { after_seq: pageParam, limit: PAGE_SIZE } } }),
      ),
    getNextPageParam: (page) => (page.length === PAGE_SIZE ? page[page.length - 1]?.seq : undefined),
  });
}

export function verifyAudit(): Promise<Verification> {
  return request(nodeApi.GET("/v1/audit/verify"));
}

export function createCheckpoint(): Promise<Checkpoint | null> {
  return request(nodeApi.POST("/v1/audit/checkpoints"));
}
