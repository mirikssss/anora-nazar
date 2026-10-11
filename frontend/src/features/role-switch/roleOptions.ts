// Варианты входа по группам «Банк (имитатор)» и «Anora Nazar» — из сидов ролей на бэке.
import type { BankRole, Identity, StaffRole } from "@/entities/session";

import type { RoleChoice } from "./useChooseRole";

export interface RoleOption {
  key: string;
  label: string;
  description: string;
  choice: RoleChoice;
}

export function bankOptions(roles: readonly BankRole[]): RoleOption[] {
  return roles.map((role) => ({
    key: `bank:${role.code}`,
    label: role.title,
    description: role.summary,
    choice: { kind: "bank", role },
  }));
}

/** У роли может быть несколько сотрудников (риск-менеджер и второй подписант) — каждый отдельно. */
export function staffOptions(roles: readonly StaffRole[]): RoleOption[] {
  return roles.flatMap((role) =>
    role.users.map((user) => ({
      key: `staff:${user.code}`,
      label: role.users.length > 1 ? user.display_name : role.title,
      description: role.summary,
      choice: { kind: "staff", role, userCode: user.code },
    })),
  );
}

export function isCurrent(option: RoleOption, identity: Identity | null): boolean {
  if (identity === null) return false;
  return option.choice.kind === "bank"
    ? identity.kind === "bank" && identity.roleCode === option.choice.role.code
    : identity.kind === "staff" && identity.userCode === option.choice.userCode;
}
