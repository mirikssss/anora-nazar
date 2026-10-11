// Подписанты: кто предложил и кто подтвердил. Второй подписант — другой сотрудник (Блок 4).
import { useStaffRoles, type VisitorSession } from "@/entities/session";

/** Имя сотрудника по коду из справочника ролей; пока справочник грузится или кода нет — сам код. */
export function useStaffName(): (code: string) => string {
  const roles = useStaffRoles().data;
  return (code) =>
    roles?.flatMap((role) => role.users).find((user) => user.code === code)?.display_name ?? code;
}

/** Действие начал текущий сотрудник: подтвердить его сам он не может. */
export function isOwnRequest(session: VisitorSession, requestedBy: string): boolean {
  return session.identity?.kind === "staff" && session.identity.userCode === requestedBy;
}
