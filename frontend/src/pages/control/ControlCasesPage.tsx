// «/control» — дела групп и программ (MOJ Case list): почему группа, заявки и их высший уровень,
// оценочная стоимость риска, срок разбора, статус и ответственный. Строка открывает дело.
import { useState } from "react";
import { useNavigate } from "react-router";

import { useCaseQueue, type CaseListItem } from "@/entities/case";
import { LevelBadge, asLevel, type Level } from "@/entities/decision";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime, formatSum } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";
import { Tabs } from "@/shared/ui/Tabs";

import { CaseStatusBadge } from "./CaseStatusBadge";
import styles from "./Control.module.css";

const t = ru.control;
const FILTERS = ["open", "closed"] as const;
type Filter = (typeof FILTERS)[number];
const PANEL_ID = "control-cases-panel";
const LEVEL_ORDER: readonly Level[] = ["red", "yellow", "green"];

/** Уровни заявок дела как есть с бэка — каждый один раз, от красного к зелёному. */
function levelsOf(item: CaseListItem): Level[] {
  const levels = new Set(item.applications.map((app) => asLevel(app.level)));
  return LEVEL_ORDER.filter((level) => levels.has(level));
}

export function ControlCasesPage() {
  const navigate = useNavigate();
  const texts = useStaffTexts().data;
  const queue = useCaseQueue("group");
  const [filter, setFilter] = useState<Filter>("open");

  const columns: Column<CaseListItem>[] = [
    {
      key: "case",
      header: t.columns.case,
      primary: true,
      render: (item) => (
        <span className={styles.caseCell}>
          <span className="num" title={item.case_id}>
            {item.case_id.slice(0, 8)}
          </span>
          <Badge tone="outline">{`${t.zone} ${String(item.zone)}`}</Badge>
        </span>
      ),
    },
    { key: "strategy", header: t.columns.strategy, render: (item) => label(t.strategies, item.strategy) },
    {
      key: "applications",
      header: t.columns.applications,
      align: "end",
      render: (item) => <span className="num">{item.applications.length}</span>,
    },
    {
      key: "levels",
      header: t.columns.levels,
      render: (item) => (
        <span className={styles.levels}>
          {levelsOf(item).map((level) => (
            <LevelBadge key={level} level={level} compact />
          ))}
        </span>
      ),
    },
    {
      key: "risk",
      header: t.columns.riskCost,
      align: "end",
      render: (item) =>
        item.risk_cost_estimate === null ? (
          ru.common.none
        ) : (
          <span className="num">
            {formatSum(item.risk_cost_estimate)} <span className={styles.muted}>{t.estimate}</span>
          </span>
        ),
    },
    {
      key: "due",
      header: t.columns.due,
      render: (item) => <span className="num">{formatDateTime(item.due_at)}</span>,
    },
    {
      key: "status",
      header: t.columns.status,
      render: (item) => (
        <CaseStatusBadge status={item.status} title={titleOf(texts?.case_statuses, item.status)} />
      ),
    },
    {
      key: "assignee",
      header: t.columns.assignee,
      render: (item) => item.assignee ?? <span className={styles.muted}>{t.unassigned}</span>,
    },
  ];

  const body = () => {
    if (queue.isPending) return <Skeleton rows={5} label={t.casesLoading} />;
    if (queue.isError)
      return (
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
      );
    const rows = queue.data.filter((item) => (item.status === "closed") === (filter === "closed"));
    if (rows.length === 0)
      return filter === "open" ? (
        <StateMessage title={t.emptyOpenTitle} description={t.emptyOpenBody} />
      ) : (
        <StateMessage title={t.emptyClosedTitle} />
      );
    return (
      <Table
        caption={t.casesCaption}
        columns={columns}
        rows={rows}
        rowKey={(item) => item.case_id}
        onRowClick={(item) => {
          void navigate(`/control/cases/${item.case_id}`);
        }}
      />
    );
  };

  return (
    <>
      <PageHeader title={t.casesTitle} subtitle={t.casesSubtitle} />
      <Card flush>
        <div className={styles.tabs}>
          <Tabs
            label={t.filterLabel}
            items={FILTERS.map((key) => ({ key, label: label(t.filters, key) }))}
            selected={filter}
            panelId={PANEL_ID}
            onSelect={(key) => {
              setFilter(key === "closed" ? "closed" : "open");
            }}
          />
        </div>
        <div id={PANEL_ID} role="tabpanel">
          {body()}
        </div>
      </Card>
    </>
  );
}
