// Клиент TanStack Query: повтор только при сбое сети, пропавшая песочница возвращает на вход.
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { sessionStore } from "@/entities/session";
import { ApiError, ERROR_CODES } from "@/shared/api";

const EXPIRED_CODES: readonly string[] = [ERROR_CODES.realmNotFound, ERROR_CODES.sandboxNotFound];
const RETRYABLE_CODES: readonly string[] = [ERROR_CODES.network, ERROR_CODES.unavailable];
const MAX_RETRIES = 1;

function onApiError(error: unknown): void {
  if (!(error instanceof ApiError)) return;
  if (EXPIRED_CODES.includes(error.code)) sessionStore.expire();
  else if (error.status === 401) sessionStore.dropIdentity();
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
  defaultOptions: {
    queries: {
      retry: (failures, error) =>
        failures < MAX_RETRIES && error instanceof ApiError && RETRYABLE_CODES.includes(error.code),
    },
  },
});

export function QueryProvider({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
