// Решение узла: уровень словом, действие, причины с источником и нормой, удержания.
// Причины состояния источников и моделей — отдельно и ниже: они не говорят о риске.
import type { ReactNode } from "react";

import { LevelBadge, ReasonItem, splitReasons, type DecisionResult } from "@/entities/decision";
import { hasPermission, useSession } from "@/entities/session";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { PERMISSIONS } from "@/shared/config/permissions";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";

import styles from "./DecisionCard.module.css";

interface DecisionCardProps {
  result: DecisionResult;
  point: string | null;
  holds?: readonly { holdId: string; requiredCheck: string }[];
  marked?: readonly string[];
  actions?: ReactNode;
}

export function DecisionCard({ result, point, holds = [], marked = [], actions }: DecisionCardProps) {
  const showScores = hasPermission(useSession(), PERMISSIONS.viewQuality);
  const texts = useStaffTexts().data;
  const { risk, system } = splitReasons(result.reasons);
  const summary: SummaryRow[] = [
    {
      key: "action",
      label: ru.decision.action,
      value: result.action ? titleOf(texts?.actions, result.action) : ru.common.none,
    },
    { key: "point", label: ru.decision.point, value: point ? label(ru.points, point) : ru.common.none },
    {
      key: "valid",
      label: ru.decision.validUntil,
      value: result.validUntil ? (
        <span className="num">{formatDateTime(result.validUntil)}</span>
      ) : (
        ru.common.none
      ),
    },
  ];
  if (result.outcome === "stopped_by_norm") {
    summary.unshift({
      key: "outcome",
      label: ru.decision.outcome,
      value: label(ru.decisionOutcomes, result.outcome),
    });
  }
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <LevelBadge level={result.level} />
        {actions !== undefined ? <div className={styles.actions}>{actions}</div> : null}
      </div>
      <SummaryList rows={summary} />

      <section className={styles.section}>
        <h3 className={styles.heading}>{ru.decision.reasons}</h3>
        {risk.length > 0 ? (
          <ul>
            {risk.map((reason, index) => (
              <ReasonItem key={`${reason.code}-${String(index)}`} reason={reason} showScores={showScores} />
            ))}
          </ul>
        ) : (
          <p className={styles.muted}>{ru.decision.reasonsEmpty}</p>
        )}
      </section>

      {holds.length > 0 ? (
        <section className={styles.section}>
          <h3 className={styles.heading}>{ru.decision.holds}</h3>
          <ul className={styles.list}>
            {holds.map((hold) => (
              <li key={hold.holdId}>
                {ru.decision.requiredCheck}: <code>{hold.requiredCheck}</code>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {marked.length > 0 ? (
        <section className={styles.section}>
          <h3 className={styles.heading}>{ru.decision.marked}</h3>
          <p className="num">{marked.join(", ")}</p>
        </section>
      ) : null}

      {system.length > 0 ? (
        <section className={styles.section}>
          <h3 className={[styles.heading, styles.muted].join(" ")}>{ru.decision.systemReasons}</h3>
          <ul>
            {system.map((reason, index) => (
              <ReasonItem key={`${reason.code}-${String(index)}`} reason={reason} showScores={showScores} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
