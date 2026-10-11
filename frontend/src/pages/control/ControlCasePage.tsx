// «/control/cases/:caseId» — дело группы или программы. Сверху граф связей; дальше решение по каждой
// заявке с её уликами (ComplyAdvantage: сначала по каждой, потом по делу), рядом безобидные объяснения,
// исход дела, ретро-поиск Т6 и лента.
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { useCase, useCaseGraph, type CaseDetail } from "@/entities/case";
import { hasPermission, useSession } from "@/entities/session";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { AssignCase } from "@/features/control-assign";
import { ParticipantDecision } from "@/features/case-decision";
import { CaseOutcome } from "@/features/case-outcome";
import { RetroSearch } from "@/features/control-retro-search";
import { ApiError, errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { label, ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { CaseGraph } from "@/widgets/case-graph/CaseGraph";
import { CaseTimeline } from "@/widgets/case-timeline/CaseTimeline";
import { CaseApplications } from "@/widgets/control-applications/CaseApplications";
import { BenignExplanations } from "@/widgets/control-benign/BenignExplanations";
import { EvidencePanel } from "@/widgets/evidence-panel/EvidencePanel";

import { CaseStatusBadge } from "./CaseStatusBadge";
import styles from "./Control.module.css";

const t = ru.control;
const SELECTED = "application";

function GraphCard({
  caseId,
  selectedId,
  onSelect,
}: {
  caseId: string;
  selectedId: string | null;
  onSelect: (applicationId: string) => void;
}) {
  const graph = useCaseGraph(caseId);
  const content = () => {
    if (graph.isPending) return <Skeleton rows={6} label={t.graph.loading} />;
    if (graph.isError)
      return (
        <StateMessage
          tone="error"
          title={t.graph.failed}
          description={errorMessage(graph.error)}
          action={
            <Button size="sm" onClick={() => void graph.refetch()}>
              {ru.common.retry}
            </Button>
          }
        />
      );
    if (graph.data.edges.length === 0) return <StateMessage title={t.graph.empty} />;
    return <CaseGraph graph={graph.data} selectedApplicationId={selectedId} onSelectApplication={onSelect} />;
  };
  return (
    <Card title={t.graph.title} subtitle={t.graph.subtitle}>
      {content()}
    </Card>
  );
}

function CaseContent({
  detail,
  fullPii,
  onRevealPii,
}: {
  detail: CaseDetail;
  fullPii: boolean;
  onRevealPii: () => void;
}) {
  const session = useSession();
  const texts = useStaffTexts().data;
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selected =
    detail.applications.find((app) => app.application_id === params.get(SELECTED)) ??
    detail.applications[0] ??
    null;
  const select = (applicationId: string) => {
    setParams({ [SELECTED]: applicationId }, { replace: true });
  };
  const decided = detail.applications.filter((app) => app.decision !== null).length;
  const meta = [
    label(t.strategies, detail.strategy),
    `${t.zone} ${String(detail.zone)}`,
    `${t.columns.due} ${formatDateTime(detail.due_at)}`,
    `${t.columns.assignee}: ${detail.assignee ?? t.unassigned}`,
  ];

  return (
    <>
      <PageHeader
        title={`${t.caseTitle} ${detail.case_id.slice(0, 8)}`}
        subtitle={meta.join(" · ")}
        tag={<CaseStatusBadge status={detail.status} title={titleOf(texts?.case_statuses, detail.status)} />}
        actions={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                void navigate("/control");
              }}
            >
              {t.backToList}
            </Button>
            <AssignCase detail={detail} />
          </>
        }
      />
      <div className={styles.page}>
        <GraphCard caseId={detail.case_id} selectedId={selected?.application_id ?? null} onSelect={select} />
        <div className={styles.columns}>
          <div className={styles.stack}>
            <Card
              title={t.applicationsTitle}
              subtitle={`${t.applicationsSubtitle} ${t.progress}: ${String(decided)} ${t.of} ${String(detail.applications.length)}.`}
              actions={
                hasPermission(session, PERMISSIONS.viewFullPii) && !fullPii ? (
                  <Button size="sm" onClick={onRevealPii}>
                    {t.showFullPii}
                  </Button>
                ) : undefined
              }
              flush
            >
              {fullPii ? <p className={styles.notice}>{t.fullPiiShown}</p> : null}
              <CaseApplications
                applications={detail.applications}
                selectedId={selected?.application_id ?? null}
                onSelect={select}
              />
            </Card>
            <Card>
              {selected === null ? (
                <StateMessage title={t.selectApplication} />
              ) : (
                <div className={styles.application}>
                  <EvidencePanel application={selected} />
                  <hr className={styles.divider} />
                  <ParticipantDecision key={selected.application_id} detail={detail} application={selected} />
                </div>
              )}
            </Card>
          </div>
          <div className={styles.stack}>
            <Card title={t.benign.title} subtitle={t.benign.subtitle}>
              <BenignExplanations items={detail.benign} />
            </Card>
            <Card title={t.outcomeTitle} subtitle={t.outcomeHint}>
              <CaseOutcome detail={detail} canDecide={hasPermission(session, PERMISSIONS.decideGroupCases)} />
            </Card>
            <Card title={t.retro.title} subtitle={t.retro.subtitle}>
              <RetroSearch caseId={detail.case_id} />
            </Card>
            <Card title={t.timelineTitle}>
              <CaseTimeline entries={detail.timeline} />
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}

export function ControlCasePage() {
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const [fullPii, setFullPii] = useState(false);
  const detail = useCase(caseId, fullPii);

  if (detail.isPending) return <Skeleton rows={8} label={t.caseLoading} />;
  if (detail.isError) {
    const notFound = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <StateMessage
        tone="error"
        title={notFound ? t.caseNotFound : ru.errors.loadFailed}
        description={notFound ? t.caseNotFoundBody : errorMessage(detail.error)}
        action={
          notFound ? (
            <Button
              size="sm"
              onClick={() => {
                void navigate("/control");
              }}
            >
              {t.backToList}
            </Button>
          ) : (
            <Button size="sm" onClick={() => void detail.refetch()}>
              {ru.common.retry}
            </Button>
          )
        }
      />
    );
  }
  return (
    <CaseContent
      detail={detail.data}
      fullPii={fullPii}
      onRevealPii={() => {
        setFullPii(true);
      }}
    />
  );
}
