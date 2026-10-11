// HTTP-клиенты узла и имитатора банка: адреса из конфигурации, песочница и токен сотрудника в заголовках,
// ошибки — ApiError. Типы путей генерируются из OpenAPI (npm run gen:api).
import createClient, { type Middleware } from "openapi-fetch";

import { env } from "@/shared/config/env";

import { networkError, toApiError } from "./errors";
import type { paths as BankPaths } from "./generated/bank-sim";
import type { paths as NodePaths } from "./generated/node";

const REALM_HEADER = "X-Realm-Id";

export interface Credentials {
  realmId: string | null;
  staffToken: string | null;
}

let readCredentials: () => Credentials = () => ({ realmId: null, staffToken: null });

/** Сессия демо регистрирует, откуда клиенты берут песочницу и токен. */
export function setCredentialsSource(source: () => Credentials): void {
  readCredentials = source;
}

function credentialsMiddleware(withToken: boolean): Middleware {
  return {
    onRequest({ request }) {
      const { realmId, staffToken } = readCredentials();
      if (realmId && !request.headers.has(REALM_HEADER)) request.headers.set(REALM_HEADER, realmId);
      if (withToken && staffToken) request.headers.set("Authorization", `Bearer ${staffToken}`);
      return request;
    },
  };
}

export const nodeApi = createClient<NodePaths>({ baseUrl: env.nodeApiBase });
nodeApi.use(credentialsMiddleware(true));

export const bankApi = createClient<BankPaths>({ baseUrl: env.bankApiBase, credentials: "same-origin" });
bankApi.use(credentialsMiddleware(false));

interface FetchResult<D> {
  data?: D;
  error?: unknown;
  response: Response;
}

/** Ответ или ApiError: сеть, недоступный сервис, ошибка бэка с понятным текстом. */
export async function request<D>(pending: Promise<FetchResult<D>>): Promise<D> {
  let result: FetchResult<D>;
  try {
    result = await pending;
  } catch {
    throw networkError();
  }
  if (!result.response.ok) throw toApiError(result.response.status, result.error);
  return result.data as D;
}
