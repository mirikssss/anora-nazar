// Центр рабочего места: по каждой заявке дела сначала уровень и причины словами с меткой источника,
// затем удержания, условия, заёмщик и данные сессии. Числового балла аналитик не видит (Блок 5).
import type { CaseApplication, CaseDetail } from "@/entities/case";
import { asLevel, LevelBadge, ReasonItem, splitReasons } from "@/entities/decision";
import { titleOf, useStaffTexts, type StaffTexts } from "@/entities/texts";
import { RevealPii } from "@/features/analyst-pii";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatSum, formatValue } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";

import styles from "./CaseSummary.module.css";
import { asReason } from "./model";

const t = ru.analyst;

export interface PiiState {
  revealed: boolean;
  pending: boolean;
  error: unknown;
  onReveal: () => void;
}

function termsRows(application: CaseApplication, texts: StaffTexts | undefined): SummaryRow[] {
  const cost = application.risk_cost_estimate;
  return [
    { key: "amount", label: t.amount, value: <span className="num">{formatSum(application.amount)}</span> },
    {
      key: "term",
      label: t.term,
      value: `${String(application.term_months)} ${ru.common.months}`,
    },
    {
      key: "cost",
      label: t.riskCost,
      value:
        cost !== null ? <span className="num">{`${formatSum(cost)} · ${t.estimate}`}</span> : ru.common.none,
    },
    { key: "action", label: t.action, value: titleOf(texts?.actions, application.action) },
    { key: "point", label: t.point, value: label(ru.points, application.point) },
  ];
}

function applicantRows(applicant: CaseApplication["applicant"]): SummaryRow[] {
  const rows: SummaryRow[] = [
    { key: "pinfl", label: t.pinfl, value: <span className="num">{applicant.pinfl}</span> },
    { key: "phone", label: t.phone, value: <span className="num">{applicant.phone}</span> },
  ];
  if (applicant.address !== null) rows.push({ key: "address", label: t.address, value: applicant.address });
  return rows;
}

function featureValue(value: number | boolean): string {
  if (typeof value === "boolean") return value ? ru.common.yes : ru.common.no;
  return formatValue(value);
}

function featureRows(features: CaseApplication["features"], texts: StaffTexts | undefined): SummaryRow[] {
  return Object.entries(features).flatMap(([code, value]) =>
    value === null
      ? []
      : [
          {
            key: code,
            label: titleOf(texts?.features, code),
            value: <span className="num">{featureValue(value)}</span>,
          },
        ],
  );
}

function ApplicationCard({ application, pii }: { application: CaseApplication; pii: PiiState }) {
  const texts = useStaffTexts().data;
  const { risk, system } = splitReasons(application.reasons.map(asReason));
  const features = featureRows(application.features, texts);
  return (
    <Card
      as="article"
      title={application.application_id}
      subtitle={label(ru.channels, application.channel)}
      actions={<LevelBadge level={asLevel(application.level)} />}
    >
      <div className={styles.body}>
        <section className={styles.section}>
          <h3 className={styles.heading}>{t.reasons}</h3>
          {risk.length > 0 ? (
            <ul>
              {risk.map((reason, index) => (
                <ReasonItem key={`${reason.code}-${String(index)}`} reason={reason} showScores={false} />
              ))}
            </ul>
          ) : (
            <p className={styles.hint}>{t.reasonsEmpty}</p>
          )}
        </section>

        {system.length > 0 || application.unavailable_sources.length > 0 ? (
          <section className={styles.section}>
            <h3 className={styles.subheading}>{t.systemReasons}</h3>
            {system.length > 0 ? (
              <ul>
                {system.map((reason, index) => (
                  <ReasonItem key={`${reason.code}-${String(index)}`} reason={reason} showScores={false} />
                ))}
              </ul>
            ) : null}
            {application.unavailable_sources.length > 0 ? (
              <p className={styles.hint}>
                {t.unavailableSources}:{" "}
                {application.unavailable_sources.map((code) => titleOf(texts?.data_sources, code)).join(", ")}
              </p>
            ) : null}
          </section>
        ) : null}

        {application.holds.length > 0 ? (
          <section className={styles.section}>
            <h3 className={styles.subheading}>{t.holds}</h3>
            <ul className={styles.holds}>
              {application.holds.map((hold) => (
                <li key={hold.hold_id} className={styles.hold}>
                  <Badge tone="orange">{titleOf(texts?.actions, hold.required_check)}</Badge>
                  <span className={styles.hint}>
                    {t.holdSince} {formatDateTime(hold.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <SummaryList rows={termsRows(application, texts)} />

        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h3 className={styles.subheading}>{t.applicant}</h3>
            {!application.applicant.full ? <span className={styles.hint}>{t.masked}</span> : null}
          </div>
          <SummaryList rows={applicantRows(application.applicant)} />
          <RevealPii {...pii} />
        </section>

        <details className={styles.features}>
          <summary className={styles.summary}>{t.features}</summary>
          {features.length > 0 ? (
            <SummaryList rows={features} />
          ) : (
            <p className={styles.hint}>{t.featuresEmpty}</p>
          )}
        </details>
      </div>
    </Card>
  );
}

function BenignCard({ benign }: { benign: CaseDetail["benign"] }) {
  const texts = useStaffTexts().data;
  return (
    <Card title={t.benign}>
      <ul className={styles.benign}>
        {benign.map((item, index) => {
          const text = texts?.benign_explanations[item.code];
          return (
            <li key={`${item.code}-${String(index)}`}>
              <span>{text?.title ?? item.code}</span>
              {text?.description ? <span className={styles.hint}>{text.description}</span> : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function CaseSummary({ detail, pii }: { detail: CaseDetail; pii: PiiState }) {
  return (
    <div className={styles.summaryStack}>
      {detail.applications.map((application) => (
        <ApplicationCard key={application.application_id} application={application} pii={pii} />
      ))}
      {detail.benign.length > 0 ? <BenignCard benign={detail.benign} /> : null}
    </div>
  );
}
