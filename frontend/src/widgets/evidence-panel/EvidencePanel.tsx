// Улики по одной заявке дела: условия, заявитель (маской или полностью), удержания, причины с порогом и
// фактом рядом, недоступные источники и все признаки. Балла модели здесь нет — его видит риск-менеджер.
import type { CaseApplication } from "@/entities/case";
import { LevelBadge, ReasonItem, asLevel, splitReasons, type Reason } from "@/entities/decision";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatSum, formatValue } from "@/shared/lib/format";
import { SummaryList } from "@/shared/ui/SummaryList";

import styles from "./EvidencePanel.module.css";

const t = ru.control.evidence;

const SOURCES: readonly string[] = ["rule", "model", "graph", "network"] satisfies Reason["source"][];
const TYPOLOGIES: readonly string[] = ["F1", "F2", "F3"] satisfies NonNullable<Reason["typology"]>[];

/** Причина дела приходит с открытыми строками; к виду причины решения приводим с проверкой кодов. */
function toReason(reason: CaseApplication["reasons"][number]): Reason | null {
  if (!SOURCES.includes(reason.source)) return null;
  const typology = reason.typology !== null && TYPOLOGIES.includes(reason.typology) ? reason.typology : null;
  return {
    ...reason,
    source: reason.source as Reason["source"],
    typology: typology as Reason["typology"],
    level: asLevel(reason.level),
  };
}

function ReasonList({ reasons }: { reasons: readonly Reason[] }) {
  return (
    <ul className={styles.reasons}>
      {reasons.map((reason, index) => (
        <ReasonItem key={`${reason.code}-${String(index)}`} reason={reason} showScores={false} />
      ))}
    </ul>
  );
}

export function EvidencePanel({ application }: { application: CaseApplication }) {
  const texts = useStaffTexts().data;
  const { risk, system } = splitReasons(
    application.reasons.flatMap((item) => {
      const reason = toReason(item);
      return reason === null ? [] : [reason];
    }),
  );
  const { applicant } = application;
  const features = Object.entries(application.features);

  return (
    <article className={styles.panel} aria-label={`${t.title} ${application.application_id}`}>
      <header className={styles.head}>
        <h3 className={styles.title}>
          <span className="num">{application.application_id}</span>
        </h3>
        <LevelBadge level={asLevel(application.level)} />
        <span className={styles.muted}>
          {label(ru.channels, application.channel)} · {label(ru.points, application.point)}
        </span>
      </header>

      <SummaryList
        rows={[
          {
            key: "amount",
            label: t.amount,
            value: <span className="num">{formatSum(application.amount)}</span>,
          },
          {
            key: "term",
            label: t.term,
            value: <span className="num">{`${String(application.term_months)} ${ru.common.months}`}</span>,
          },
          {
            key: "risk",
            label: t.riskCost,
            value:
              application.risk_cost_estimate === null ? (
                ru.common.none
              ) : (
                <span className="num">
                  {formatSum(application.risk_cost_estimate)} · {ru.control.estimate}
                </span>
              ),
          },
          { key: "pinfl", label: t.pinfl, value: <span className="num">{applicant.pinfl}</span> },
          { key: "phone", label: t.phone, value: <span className="num">{applicant.phone}</span> },
          {
            key: "address",
            label: t.address,
            value: applicant.address ?? (applicant.full ? ru.common.none : t.masked),
          },
        ]}
      />

      <section className={styles.section}>
        <h4 className={styles.heading}>{t.holds}</h4>
        {application.holds.length === 0 ? (
          <p className={styles.muted}>{t.noHolds}</p>
        ) : (
          <ul className={styles.list}>
            {application.holds.map((hold) => (
              <li key={hold.hold_id}>
                {titleOf(texts?.actions, hold.required_check)}{" "}
                <span className={styles.muted}>
                  {t.holdSince} {formatDateTime(hold.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h4 className={styles.heading}>{t.reasons}</h4>
        {risk.length > 0 ? <ReasonList reasons={risk} /> : <p className={styles.muted}>{t.noReasons}</p>}
      </section>

      {system.length > 0 || application.unavailable_sources.length > 0 ? (
        <section className={styles.section}>
          <h4 className={[styles.heading, styles.muted].join(" ")}>{t.systemReasons}</h4>
          {application.unavailable_sources.length > 0 ? (
            <p className={styles.muted}>
              {t.unavailable}:{" "}
              {application.unavailable_sources.map((code) => titleOf(texts?.data_sources, code)).join(", ")}
            </p>
          ) : null}
          {system.length > 0 ? <ReasonList reasons={system} /> : null}
        </section>
      ) : null}

      {features.length > 0 ? (
        <details className={styles.features}>
          <summary>
            {t.features} <span className={styles.muted}>{features.length}</span>
          </summary>
          <dl className={styles.featureList}>
            {features.map(([code, value]) => (
              <div key={code} className={styles.feature}>
                <dt>{titleOf(texts?.features, code)}</dt>
                <dd className="num">{formatValue(value)}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </article>
  );
}
