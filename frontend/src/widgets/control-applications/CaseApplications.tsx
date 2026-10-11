// Заявки дела списком: уровень, сумма, удержания и решение по каждой. Выбор строки открывает улики.
import type { CaseApplication } from "@/entities/case";
import { LevelBadge, asLevel } from "@/entities/decision";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { ru } from "@/shared/i18n/ru";
import { formatSum } from "@/shared/lib/format";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./CaseApplications.module.css";

const t = ru.control;

interface CaseApplicationsProps {
  applications: readonly CaseApplication[];
  selectedId: string | null;
  onSelect: (applicationId: string) => void;
}

export function CaseApplications({ applications, selectedId, onSelect }: CaseApplicationsProps) {
  const texts = useStaffTexts().data;
  const columns: Column<CaseApplication>[] = [
    {
      key: "id",
      header: t.applicationColumn,
      primary: true,
      render: (app) => <span className="num">{app.application_id}</span>,
    },
    {
      key: "level",
      header: t.levelColumn,
      render: (app) => <LevelBadge level={asLevel(app.level)} compact />,
    },
    {
      key: "amount",
      header: t.evidence.amount,
      align: "end",
      render: (app) => <span className="num">{formatSum(app.amount)}</span>,
    },
    {
      key: "holds",
      header: t.evidence.holds,
      align: "end",
      render: (app) => <span className="num">{app.holds.length}</span>,
    },
    {
      key: "decision",
      header: t.decisionColumn,
      render: (app) =>
        app.decision === null ? (
          <span className={styles.muted}>{t.noDecision}</span>
        ) : (
          titleOf(texts?.participant_actions, app.decision)
        ),
    },
  ];
  return (
    <Table
      caption={t.applicationsCaption}
      columns={columns}
      rows={applications}
      rowKey={(app) => app.application_id}
      selectedKey={selectedId}
      onRowClick={(app) => {
        onSelect(app.application_id);
      }}
    />
  );
}
