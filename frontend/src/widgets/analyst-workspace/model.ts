// Пути рабочего места аналитика и приведение причины дела к причине решения.
import type { CaseApplication } from "@/entities/case";
import { asLevel, type Reason } from "@/entities/decision";

export const QUEUE_PATH = "/analyst";

export function casePath(caseId: string): string {
  return `${QUEUE_PATH}/cases/${caseId}`;
}

/** Дело отдаёт ту же причину из записи решения, но в OpenAPI источник и типология — строки, а не перечисления. */
export function asReason(reason: CaseApplication["reasons"][number]): Reason {
  return {
    ...reason,
    level: asLevel(reason.level),
    source: reason.source as Reason["source"],
    typology: reason.typology as Reason["typology"],
  };
}
