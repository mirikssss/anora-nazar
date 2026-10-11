// Очереди дел: сколько ждёт разбора в антифрод-центре и во внутреннем контроле. Названия очередей —
// из каталога текстов; пустая очередь в ответе не приходит, поэтому список берём из каталога и ответа вместе.
import { Link } from "react-router";

import { titleOf, useStaffTexts } from "@/entities/texts";
import { IconForward } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";

import styles from "./QueueSummary.module.css";

const t = ru.risk.overview;

/** Страница очереди в интерфейсе (таблица «Роли и страницы»). */
const QUEUE_PATHS: Readonly<Record<string, string>> = {
  online: "/analyst",
  group: "/control",
};

export function QueueSummary({ queues }: { queues: Readonly<Record<string, number>> }) {
  const catalog = useStaffTexts().data?.queues;
  const codes = [...new Set([...Object.keys(catalog ?? {}), ...Object.keys(queues)])];
  return (
    <Card title={t.queuesTitle}>
      <ul className={styles.list}>
        {codes.map((code) => {
          const path = QUEUE_PATHS[code];
          const description = catalog?.[code]?.description ?? null;
          return (
            <li key={code} className={styles.item}>
              <div className={styles.text}>
                {path === undefined ? (
                  <span className={styles.title}>{titleOf(catalog, code)}</span>
                ) : (
                  <Link to={path} className={styles.link}>
                    {titleOf(catalog, code)}
                    <IconForward size={16} aria-hidden />
                  </Link>
                )}
                {description !== null ? <p className={styles.description}>{description}</p> : null}
              </div>
              <p className={styles.count}>
                <span className={styles.value}>{formatNumber(queues[code] ?? 0)}</span>
                <span className={styles.unit}>{t.queueCount}</span>
              </p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
