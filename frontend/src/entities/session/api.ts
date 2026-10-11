// Роли, песочница и демо-вход: запросы к узлу и имитатору банка.
import { useQuery } from "@tanstack/react-query";

import { bankApi, nodeApi, request, type BankSchemas, type NodeSchemas } from "@/shared/api";

export type StaffRole = NodeSchemas["schemas"]["StaffRoleOut"];
export type BankRole = BankSchemas["schemas"]["BankRoleOut"];
export type Me = NodeSchemas["schemas"]["MeOut"];

export const sessionKeys = {
  staffRoles: ["session", "staff-roles"] as const,
  bankRoles: ["session", "bank-roles"] as const,
};

export function useStaffRoles() {
  return useQuery({
    queryKey: sessionKeys.staffRoles,
    queryFn: () => request(nodeApi.GET("/v1/staff/roles")),
    staleTime: Infinity,
  });
}

export function useBankRoles() {
  return useQuery({
    queryKey: sessionKeys.bankRoles,
    queryFn: () => request(bankApi.GET("/v1/roles")),
    staleTime: Infinity,
  });
}

export async function createSandbox(): Promise<string> {
  const sandbox = await request(bankApi.POST("/v1/sandboxes"));
  return sandbox.realm_id;
}

export async function deleteSandbox(): Promise<void> {
  await request(bankApi.DELETE("/v1/sandboxes/current"));
}

export async function demoLogin(userCode: string): Promise<{ token: string; me: Me }> {
  return request(nodeApi.POST("/v1/auth/demo-login", { body: { user_code: userCode } }));
}
