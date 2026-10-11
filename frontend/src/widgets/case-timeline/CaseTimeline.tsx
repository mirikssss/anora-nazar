// Лента дела (MOJ Timeline): кто, когда, что сделал; та же запись, что ушла в журнал (№ записи).
import type { CaseDetail } from "@/entities/case";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatValue } from "@/shared/lib/format";

import styles from "./CaseTimeline.module.css";

type Entry = CaseDetail["timeline"][number];

function details(entry: Entry, texts: ReturnType<typeof useStaffTexts>["data"]): string {
  const { payload } = entry;
  const parts: string[] = [];
  if (typeof payload.application_id === "string") parts.push(payload.application_id);
  if (typeof payload.level === "string") parts.push(titleOf(texts?.levels, payload.level));
  if (typeof payload.action === "string") parts.push(titleOf(texts?.participant_actions, payload.action));
  if (typeof payload.outcome === "string") parts.push(titleOf(texts?.case_outcomes, payload.outcome));
  if (typeof payload.basis === "string") parts.push(payload.basis);
  if (typeof payload.note === "string" && payload.note !== "") parts.push(payload.note);
  if (typeof payload.matches === "number")
    parts.push(`${ru.caseTimeline.matches}: ${formatValue(payload.matches)}`);
  return parts.join(" · ");
}

export function CaseTimeline({ entries }: { entries: readonly Entry[] }) {
  const texts = useStaffTexts().data;
  const ordered = [...entries].sort((a, b) => b.at.localeCompare(a.at));
  return (
    <ol className={styles.timeline} aria-label={ru.caseTimeline.title}>
      {ordered.map((entry) => (
        <li key={entry.audit_seq} className={styles.entry}>
          <div className={styles.head}>
            <span className={styles.kind}>{label(ru.caseTimeline.kinds, entry.kind)}</span>
            <span className={styles.meta}>
              {formatDateTime(entry.at)} · {entry.actor === "system" ? ru.caseTimeline.system : entry.actor} ·{" "}
              {ru.caseTimeline.audit} {entry.audit_seq}
            </span>
          </div>
          {details(entry, texts) !== "" ? <p className={styles.details}>{details(entry, texts)}</p> : null}
        </li>
      ))}
    </ol>
  );
}
