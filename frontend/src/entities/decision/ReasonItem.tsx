// Причина: код (тексты придут из каталога бэка), источник, типология, норма и доказательства.
import { label, ru } from "@/shared/i18n/ru";
import { formatValue } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";

import type { Reason } from "./model";
import styles from "./ReasonItem.module.css";

export function ReasonItem({ reason }: { reason: Reason }) {
  const facts = reason.evidence.flatMap((item) => Object.entries(item));
  return (
    <li className={styles.reason}>
      <div className={styles.head}>
        <Badge tone="outline">{label(ru.reasonSources, reason.source)}</Badge>
        <code className={styles.code}>{reason.code}</code>
      </div>
      <div className={styles.meta}>
        {reason.typology !== null ? <span>{reason.typology}</span> : null}
        {reason.norm !== null ? (
          <span>
            {ru.decision.norm}: {reason.norm}
          </span>
        ) : null}
        {reason.level !== null ? <span>{label(ru.levels, reason.level)}</span> : null}
      </div>
      {facts.length > 0 ? (
        <dl className={styles.evidence} aria-label={ru.decision.evidence}>
          {facts.map(([key, value], index) => (
            <div key={`${key}-${String(index)}`} className={styles.fact}>
              <dt>{key}</dt>
              <dd className="num">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </li>
  );
}
