// Сессия посетителя демо: его песочница и под какой ролью он смотрит.
// Хранится в браузере как сессия зрителя (не данные продукта): ключ песочницы и токен демо-входа,
// чтобы перезагрузка страницы не теряла песочницу. Всё остальное — только с бэка.
import { useSyncExternalStore } from "react";

import { setCredentialsSource } from "@/shared/api";

export interface StaffIdentity {
  kind: "staff";
  roleCode: string;
  userCode: string;
  displayName: string;
  division: string;
  permissions: readonly string[];
  token: string;
}

export interface BankIdentity {
  kind: "bank";
  roleCode: string;
  title: string;
  permissions: readonly string[];
}

export type Identity = StaffIdentity | BankIdentity;

export interface VisitorSession {
  realmId: string | null;
  identity: Identity | null;
  /** Песочница пропала (сброшена или удалена по сроку) — показать, почему вернули на вход. */
  expired: boolean;
}

const STORAGE_KEY = "anora-nazar.session";
const EMPTY: VisitorSession = { realmId: null, identity: null, expired: false };

function isSession(value: unknown): value is VisitorSession {
  if (typeof value !== "object" || value === null || !("realmId" in value) || !("identity" in value))
    return false;
  const identity = value.identity;
  // Сессия из прежней версии интерфейса без прав роли — роль выбирается заново.
  return identity === null || (typeof identity === "object" && "permissions" in identity);
}

function load(): VisitorSession {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    return isSession(parsed) ? { ...parsed, expired: false } : EMPTY;
  } catch {
    return EMPTY;
  }
}

let current = load();
const listeners = new Set<() => void>();

function save(next: VisitorSession): void {
  current = next;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ realmId: next.realmId, identity: next.identity }));
  } catch {
    // Хранилище недоступно (приватный режим): сессия живёт до перезагрузки.
  }
  listeners.forEach((listener) => {
    listener();
  });
}

setCredentialsSource(() => ({
  realmId: current.realmId,
  staffToken: current.identity?.kind === "staff" ? current.identity.token : null,
}));

export const sessionStore = {
  get: (): VisitorSession => current,
  subscribe: (listener: () => void): (() => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  startRealm(realmId: string): void {
    save({ realmId, identity: null, expired: false });
  },
  setIdentity(identity: Identity): void {
    save({ ...current, identity, expired: false });
  },
  /** Сброс демо: песочница удалена по просьбе посетителя. */
  clear(): void {
    save(EMPTY);
  },
  /** Песочница исчезла на бэке: возвращаем на вход с объяснением. */
  expire(): void {
    if (current.realmId !== null) save({ ...EMPTY, expired: true });
  },
  /** Токен сотрудника отклонён: роль нужно выбрать заново, песочница остаётся. */
  dropIdentity(): void {
    save({ ...current, identity: null });
  },
};

export function useSession(): VisitorSession {
  return useSyncExternalStore(sessionStore.subscribe, sessionStore.get);
}

export function hasPermission(session: VisitorSession, permission: string): boolean {
  return session.identity?.permissions.includes(permission) ?? false;
}
