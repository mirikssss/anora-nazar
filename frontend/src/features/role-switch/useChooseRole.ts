// Войти в роль: песочница создаётся при первом входе, сотрудник узла получает токен демо-входа.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import {
  createSandbox,
  demoLogin,
  sessionKeys,
  sessionStore,
  type BankRole,
  type StaffRole,
} from "@/entities/session";

export type RoleChoice =
  { kind: "staff"; role: StaffRole; userCode: string } | { kind: "bank"; role: BankRole };

async function enter(choice: RoleChoice): Promise<string> {
  if (sessionStore.get().realmId === null) sessionStore.startRealm(await createSandbox());
  if (choice.kind === "bank") {
    sessionStore.setIdentity({
      kind: "bank",
      roleCode: choice.role.code,
      title: choice.role.title,
      permissions: choice.role.permissions,
    });
    return choice.role.home_path;
  }
  const { token, me } = await demoLogin(choice.userCode);
  sessionStore.setIdentity({
    kind: "staff",
    roleCode: me.role_code,
    userCode: me.user_code,
    displayName: me.display_name,
    division: me.division,
    permissions: me.permissions,
    token,
  });
  return choice.role.home_path;
}

export function useChooseRole() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: enter,
    onSuccess: async (homePath) => {
      // Права другой роли — другие ответы: кеш прежней роли не переиспользуем.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== sessionKeys.staffRoles[0],
      });
      await navigate(homePath);
    },
  });
}
