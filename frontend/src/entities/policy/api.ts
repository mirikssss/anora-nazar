// Действующая политика контура, предложения порогов и их подтверждение вторым подписантом.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type PolicyOverview = NodeSchemas["schemas"]["PolicyOverviewOut"];
export type Threshold = NodeSchemas["schemas"]["EditableThreshold"];
export type Proposal = NodeSchemas["schemas"]["ProposalOut"];
export type ProposalInput = NodeSchemas["schemas"]["ProposalIn"];

export const policyKeys = {
  overview: ["policy"] as const,
};

export function usePolicy() {
  return useQuery({
    queryKey: policyKeys.overview,
    queryFn: () => request(nodeApi.GET("/v1/policy")),
  });
}

export function proposeChange(input: ProposalInput): Promise<Proposal> {
  return request(nodeApi.POST("/v1/policy/proposals", { body: input }));
}

export function approveProposal(proposalId: string): Promise<Proposal> {
  return request(
    nodeApi.POST("/v1/policy/proposals/{proposal_id}/approval", {
      params: { path: { proposal_id: proposalId } },
    }),
  );
}
