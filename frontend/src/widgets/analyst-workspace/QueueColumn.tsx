// Очередь антифрод-центра (Stripe Radar): порядок — с бэка, по оценочной стоимости риска; балла нет.
// J и K переключают дела с любого места страницы, кроме полей ввода; Enter на строке открывает дело.
import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router";

import { useCaseQueue, type CaseListItem } from "@/entities/case";
import { asLevel, LevelBadge } from "@/entities/decision";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime, formatSum } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import { casePath } from "./model";
import styles from "./QueueColumn.module.css";

const t = ru.analyst;
const CHECKABLE_INPUTS: readonly string[] = ["checkbox", "radio", "button", "submit"];

function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (
    target.isContentEditable ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  )
    return true;
  return target instanceof HTMLInputElement && !CHECKABLE_INPUTS.includes(target.type);
}

/** Следующее (+1) или предыдущее (−1) дело; без выбранного — первое в очереди. */
function neighbour(ids: readonly string[], currentId: string | null, step: 1 | -1): string | undefined {
  const index = currentId === null ? -1 : ids.indexOf(currentId);
  if (index === -1) return ids[0];
  return ids[Math.min(Math.max(index + step, 0), ids.length - 1)];
}

function useQueueHotkeys(ids: readonly string[], currentId: string | null, open: (caseId: string) => void) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isTextEntry(event.target)) return;
      // По коду клавиши, а не по символу: в русской раскладке J и K — это «о» и «л».
      const step = event.code === "KeyJ" ? 1 : event.code === "KeyK" ? -1 : null;
      if (step === null) return;
      const target = neighbour(ids, currentId, step);
      if (target === undefined || target === currentId) return;
      event.preventDefault();
      open(target);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [ids, currentId, open]);
}

interface QueueRowProps {
  item: CaseListItem;
  active: boolean;
  linkRef: (element: HTMLAnchorElement | null) => void;
}

function QueueRow({ item, active, linkRef }: QueueRowProps) {
  const texts = useStaffTexts().data;
  const lead = item.applications[0];
  const escalated = item.escalated_at !== null;
  return (
    <li>
      <Link
        ref={linkRef}
        to={casePath(item.case_id)}
        className={[styles.row, active ? styles.active : ""].join(" ")}
        aria-current={active ? "page" : undefined}
      >
        <span className={styles.level}>
          <LevelBadge level={asLevel(lead?.level)} compact />
        </span>
        <span className={styles.ids}>
          {item.applications.map((application) => application.application_id).join(", ")}
        </span>
        <span className={`${styles.cost} num`}>
          {item.risk_cost_estimate !== null ? formatSum(item.risk_cost_estimate) : ru.common.none}
        </span>
        <span className={[styles.meta, escalated ? styles.escalated : ""].join(" ")}>
          {titleOf(texts?.case_statuses, item.status)} · {t.due} {formatDateTime(item.due_at)}
        </span>
        <span className={styles.estimate}>{t.estimate}</span>
      </Link>
    </li>
  );
}

export function QueueColumn({ currentId }: { currentId: string | null }) {
  const queue = useCaseQueue("online");
  const navigate = useNavigate();
  const links = useRef(new Map<string, HTMLAnchorElement>());
  const cases = queue.data ?? [];
  const ids = cases.map((item) => item.case_id);
  const idsKey = ids.join(",");

  useEffect(() => {
    if (currentId !== null) links.current.get(currentId)?.scrollIntoView({ block: "nearest" });
  }, [currentId, idsKey]);

  useQueueHotkeys(ids, currentId, (caseId) => {
    links.current.get(caseId)?.focus({ preventScroll: true });
    void navigate(casePath(caseId));
  });

  return (
    <Card
      flush
      title={t.queue}
      subtitle={<span className={styles.hotkeys}>{t.hotkeys}</span>}
      actions={queue.data !== undefined ? <Badge>{String(cases.length)}</Badge> : undefined}
    >
      {queue.isPending ? (
        <div className={styles.state}>
          <Skeleton rows={5} label={t.queueLoading} />
        </div>
      ) : queue.isError ? (
        <StateMessage
          tone="error"
          title={ru.errors.loadFailed}
          description={errorMessage(queue.error)}
          action={
            <Button size="sm" onClick={() => void queue.refetch()}>
              {ru.common.retry}
            </Button>
          }
        />
      ) : cases.length === 0 ? (
        <StateMessage title={t.queueEmpty} description={t.queueEmptyHint} />
      ) : (
        <ol className={styles.list} aria-label={t.queue}>
          {cases.map((item) => (
            <QueueRow
              key={item.case_id}
              item={item}
              active={item.case_id === currentId}
              linkRef={(element) => {
                if (element === null) links.current.delete(item.case_id);
                else links.current.set(item.case_id, element);
              }}
            />
          ))}
        </ol>
      )}
    </Card>
  );
}
