// Правила и счётчики оператора приходят без схемы в OpenAPI: читаем только нужные поля с проверкой типа.
import { asLevel, type Level } from "@/entities/decision";
import { list, num, obj, str } from "@/shared/lib/json";

import type { NetworkOverview } from "./api";

export interface NetworkRule {
  code: string;
  counter: string;
  min: number | null;
  /** null — сигнал только улика: уровень даёт сочетание сигналов. */
  level: Level | null;
}

export interface LenderCounters {
  lender: string;
  contour: string;
  applications: number;
  events: number;
  confirmedResults: number;
  queries: number;
  quotaUsed: number;
  quotaLimit: number | null;
  activeWatches: number;
  delivered: number;
  pending: number;
  failed: number;
}

export function networkRules(overview: NetworkOverview): NetworkRule[] {
  return overview.rules.flatMap((rule) => {
    const code = str(rule.code);
    if (code === null) return [];
    return [{ code, counter: str(rule.counter) ?? "", min: num(rule.min), level: asLevel(str(rule.level)) }];
  });
}

/** Счётчики по кредитору и контуру; null — оператор не ответил. */
export function lenderCounters(overview: NetworkOverview): LenderCounters[] | null {
  if (overview.operator === null) return null;
  return list(overview.operator.lenders).flatMap((item) => {
    const row = obj(item);
    const lender = str(row?.lender);
    if (row === null || lender === null) return [];
    const quota = obj(row.quota);
    const notifications = obj(row.notifications);
    return [
      {
        lender,
        contour: str(row.contour) ?? "",
        applications: num(row.applications) ?? 0,
        events: num(row.events) ?? 0,
        confirmedResults: num(row.confirmed_results) ?? 0,
        queries: num(row.queries) ?? 0,
        quotaUsed: num(quota?.used) ?? 0,
        quotaLimit: num(quota?.limit),
        activeWatches: num(row.active_watches) ?? 0,
        delivered: num(notifications?.delivered) ?? 0,
        pending: num(notifications?.pending) ?? 0,
        failed: num(notifications?.failed) ?? 0,
      },
    ];
  });
}
