// Типизированная ошибка API с текстом для человека. Формат бэка: {"error": {code, message, details}}.
import { ru } from "@/shared/i18n/ru";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    /** Ошибки полей формы: путь поля через точку → текст. */
    readonly fields: Readonly<Record<string, string>> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Коды, по которым интерфейс ведёт себя по-особому. */
export const ERROR_CODES = {
  network: "network",
  unavailable: "unavailable",
  validation: "validation",
  realmNotFound: "realm_not_found",
  sandboxNotFound: "sandbox_not_found",
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function fieldErrors(detail: unknown[]): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const item of detail) {
    if (!isRecord(item) || !Array.isArray(item.loc) || typeof item.msg !== "string") continue;
    // loc начинается с «body»: путь поля — без него.
    const path = item.loc.slice(1).map(String).join(".");
    fields[path] = item.msg.replace(/^Value error, /, "");
  }
  return fields;
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error)) {
    const { code, message, details } = body.error;
    if (typeof code === "string" && typeof message === "string") {
      const fields =
        isRecord(details) && isRecord(details.fields) ? (details.fields as Record<string, string>) : {};
      return new ApiError(status, code, message, fields);
    }
  }
  if (isRecord(body) && Array.isArray(body.detail)) {
    return new ApiError(status, ERROR_CODES.validation, ru.errors.validation, fieldErrors(body.detail));
  }
  if (status === 502 || status === 503 || status === 504) {
    return new ApiError(status, ERROR_CODES.unavailable, ru.errors.unavailable);
  }
  return new ApiError(status, "unknown", ru.errors.unknown);
}

export function networkError(): ApiError {
  return new ApiError(0, ERROR_CODES.network, ru.errors.network);
}

/** Текст любой ошибки для показа человеку. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : ru.errors.unknown;
}
