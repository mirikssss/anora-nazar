// Заявка конвейера банка: что видит имитатор и что ответил узел.
import type { BankSchemas } from "@/shared/api";

import { parseResult, type DecisionResult } from "@/entities/decision";

export type Application = BankSchemas["schemas"]["ApplicationOut"];
export type ApplicationDraft = BankSchemas["schemas"]["ApplicationDraft"];
export type ApplicationChange = BankSchemas["schemas"]["ApplicationChange"];

export interface LastDecision extends DecisionResult {
  decisionId: string | null;
  point: string | null;
  holds: { holdId: string; requiredCheck: string }[];
  marked: string[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** last_decision — ответ узла (DecisionOut), сохранённый конвейером как JSON. */
export function lastDecision(application: Application): LastDecision | null {
  const raw = application.last_decision;
  if (!raw) return null;
  const holds = Array.isArray(raw.holds) ? raw.holds.filter(isObject) : [];
  return {
    ...parseResult(raw),
    decisionId: typeof raw.decision_id === "string" ? raw.decision_id : null,
    point: typeof raw.point === "string" ? raw.point : null,
    holds: holds.map((hold) => ({
      holdId: String(hold.hold_id),
      requiredCheck: String(hold.required_check),
    })),
    marked: Array.isArray(raw.marked_applications) ? raw.marked_applications.map(String) : [],
  };
}

interface SnapshotView {
  amount: number | null;
  termMonths: number | null;
  purpose: string | null;
  pinfl: string | null;
  phone: string | null;
  deviceId: string | null;
  branchId: string | null;
  employeeId: string | null;
  account: string | null;
  mandatory: Record<string, unknown> | null;
  program: Record<string, unknown> | null;
}

function field(source: Record<string, unknown> | null, key: string): unknown {
  return source?.[key];
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function num(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

/** Снимок заявки — контракт ApplicationSnapshot; в ответе конвейера он приходит как JSON. */
export function snapshotView(application: Application): SnapshotView {
  const snapshot = application.snapshot;
  const loan = isObject(snapshot.loan) ? snapshot.loan : null;
  const applicant = isObject(snapshot.applicant) ? snapshot.applicant : null;
  return {
    amount: num(field(loan, "amount")),
    termMonths: num(field(loan, "term_months")),
    purpose: str(field(loan, "purpose")),
    pinfl: str(field(applicant, "pinfl")),
    phone: str(field(applicant, "phone")),
    deviceId: str(field(applicant, "device_id")),
    branchId: str(snapshot.branch_id),
    employeeId: str(snapshot.employee_id),
    account: str(snapshot.disbursement_account),
    mandatory: isObject(snapshot.mandatory_checks) ? snapshot.mandatory_checks : null,
    program: isObject(snapshot.program) ? snapshot.program : null,
  };
}
