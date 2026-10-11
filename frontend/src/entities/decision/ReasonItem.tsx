// Причина: формулировка из каталога текстов (node/texts), источник, норма и доказательства.
// У причины модели балл и вклад признаков видит только риск-менеджер (Блок 5, п. 5); остальным —
// сигналы словами, из-за которых модель подняла уровень.
import { titleOf, useStaffTexts, type StaffTexts } from "@/entities/texts";
import { ru } from "@/shared/i18n/ru";
import { formatDecimal, formatShare, formatSum, formatValue } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";

import { modelEvidence, type ModelEvidence, type Reason } from "./model";
import styles from "./ReasonItem.module.css";

function Facts({ facts }: { facts: readonly [string, unknown][] }) {
  if (facts.length === 0) return null;
  return (
    <dl className={styles.evidence} aria-label={ru.decision.evidence}>
      {facts.map(([key, value], index) => (
        <div key={`${key}-${String(index)}`} className={styles.fact}>
          <dt>{key}</dt>
          <dd className="num">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

interface ModelFactsProps {
  evidence: ModelEvidence;
  showScores: boolean;
  texts: StaffTexts | undefined;
}

function ModelFacts({ evidence, showScores, texts }: ModelFactsProps) {
  const signals = [
    ...new Set(evidence.contributions.flatMap((item) => (item.reasonCode ? [item.reasonCode] : []))),
  ];
  const facts: [string, unknown][] = [];
  if (showScores) {
    if (evidence.probability !== null)
      facts.push([ru.decision.probability, formatShare(evidence.probability)]);
    if (evidence.riskCost !== null) {
      const cost = formatSum(evidence.riskCost);
      facts.push([
        ru.decision.riskCost,
        evidence.riskCostIsEstimate ? `${cost} · ${ru.decision.estimate}` : cost,
      ]);
    }
    for (const item of evidence.contributions) {
      facts.push([
        titleOf(texts?.features, item.feature),
        `${formatValue(item.value)} · ${ru.decision.contribution} ${formatDecimal(item.contribution, 3)}`,
      ]);
    }
  }
  return (
    <>
      {signals.length > 0 ? (
        <ul className={styles.signals} aria-label={ru.decision.signals}>
          {signals.map((code) => (
            <li key={code}>{titleOf(texts?.reasons, code)}</li>
          ))}
        </ul>
      ) : null}
      <Facts facts={facts} />
    </>
  );
}

export function ReasonItem({ reason, showScores }: { reason: Reason; showScores: boolean }) {
  const texts = useStaffTexts().data;
  const text = texts?.reasons[reason.code];
  const model = modelEvidence(reason);
  return (
    <li className={styles.reason}>
      <div className={styles.head}>
        <Badge tone="outline">{titleOf(texts?.reason_sources, reason.source)}</Badge>
        <span className={styles.title}>{text?.title ?? reason.code}</span>
      </div>
      {text !== undefined ? <p className={styles.explanation}>{text.explanation}</p> : null}
      <div className={styles.meta}>
        <code>{reason.code}</code>
        {reason.typology !== null ? <span>{reason.typology}</span> : null}
        {reason.norm !== null ? (
          <span>
            {ru.decision.norm}: {reason.norm}
          </span>
        ) : null}
        {reason.level !== null ? <span>{titleOf(texts?.levels, reason.level)}</span> : null}
      </div>
      {model !== null ? (
        <ModelFacts evidence={model} showScores={showScores} texts={texts} />
      ) : (
        <Facts facts={reason.evidence.flatMap((item) => Object.entries(item))} />
      )}
    </li>
  );
}
