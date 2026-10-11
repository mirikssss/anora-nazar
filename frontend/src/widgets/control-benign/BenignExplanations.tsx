// Безобидные объяснения связи (Блок 2, шаг 3): домохозяйство, зарплатный проект, плановый набор.
// Это факты для проверяющего, а не вывод — поэтому они стоят рядом с уликами, до решения.
import type { CaseDetail } from "@/entities/case";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { label, ru } from "@/shared/i18n/ru";
import { formatValue } from "@/shared/lib/format";

import styles from "./BenignExplanations.module.css";

const t = ru.control.benign;

export function BenignExplanations({ items }: { items: CaseDetail["benign"] }) {
  const texts = useStaffTexts().data;
  if (items.length === 0) return <p className={styles.muted}>{t.empty}</p>;
  return (
    <ul className={styles.list}>
      {items.map((item) => {
        const description = texts?.benign_explanations[item.code]?.description;
        const facts = Object.entries(item.evidence);
        return (
          <li key={item.code} className={styles.item}>
            <span className={styles.title}>{titleOf(texts?.benign_explanations, item.code)}</span>
            {description ? <span className={styles.muted}>{description}</span> : null}
            {facts.length > 0 ? (
              <span className={styles.facts}>
                {facts.map(([key, value]) => (
                  <span key={key}>
                    {label(t.evidence, key)}: <span className="num">{formatValue(value)}</span>
                  </span>
                ))}
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
