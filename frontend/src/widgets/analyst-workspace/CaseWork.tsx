// Правая колонка: статус и срок дела, «взять в работу», звонок с исходом и лента дела.
import type { CaseDetail } from "@/entities/case";
import { hasPermission, useSession } from "@/entities/session";
import { titleOf, useStaffTexts, type StaffTexts } from "@/entities/texts";
import { AssignCaseButton } from "@/features/analyst-assign";
import { CaseOutcome } from "@/features/case-outcome";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";
import { CaseTimeline } from "@/widgets/case-timeline/CaseTimeline";

import styles from "./CaseWork.module.css";

const t = ru.analyst;

function workRows(detail: CaseDetail, texts: StaffTexts | undefined): SummaryRow[] {
  const rows: SummaryRow[] = [
    {
      key: "status",
      label: t.status,
      value: (
        <Badge tone={detail.escalated_at !== null ? "orange" : "neutral"}>
          {titleOf(texts?.case_statuses, detail.status)}
        </Badge>
      ),
    },
    { key: "assignee", label: t.assignee, value: detail.assignee ?? t.unassigned },
    { key: "due", label: t.due, value: <span className="num">{formatDateTime(detail.due_at)}</span> },
  ];
  if (detail.escalated_at !== null) {
    rows.push({
      key: "escalated",
      label: t.escalated,
      value: <span className="num">{formatDateTime(detail.escalated_at)}</span>,
    });
  }
  rows.push({
    key: "zone",
    label: t.zone,
    value: `${String(detail.zone)} · ${titleOf(texts?.queues, detail.queue)}`,
  });
  return rows;
}

export function CaseWork({ detail }: { detail: CaseDetail }) {
  const texts = useStaffTexts().data;
  const canDecide = hasPermission(useSession(), PERMISSIONS.decideOnlineCases);
  return (
    <>
      <Card title={t.work}>
        <div className={styles.work}>
          <SummaryList rows={workRows(detail, texts)} />
          {canDecide && detail.status === "open" ? <AssignCaseButton caseId={detail.case_id} /> : null}
        </div>
      </Card>
      <Card title={t.callAndOutcome}>
        <CaseOutcome key={detail.case_id} detail={detail} canDecide={canDecide} />
      </Card>
      <Card title={t.timeline}>
        <CaseTimeline entries={detail.timeline} />
      </Card>
    </>
  );
}
