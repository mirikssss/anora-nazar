// Готовые сценарии трёх зон в один клик: что произойдёт, запуск через конвейер банка, ответ узла по заявкам.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { applicationKeys } from "@/entities/application";
import { borrowerKeys } from "@/entities/borrower";
import { asLevel, LevelBadge } from "@/entities/decision";
import {
  latestRun,
  runDecisionId,
  runError,
  runScenario,
  scenarioKeys,
  useScenarioRuns,
  useScenarios,
  type RunApplication,
  type Scenario,
  type ScenarioRun,
} from "@/entities/scenario";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { IconDecision, IconForward } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { formatTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import styles from "./ScenarioPicker.module.css";

const t = ru.borrower.scenarios;
const CONTROL_ZONE = "control";

function RunResult({
  item,
  onOpenApplication,
}: {
  item: RunApplication;
  onOpenApplication: (applicationId: string) => void;
}) {
  const actions = useStaffTexts().data?.actions;
  const decisionId = runDecisionId(item);
  const error = runError(item);
  const applicationId = item.application_id;
  return (
    <li className={styles.result}>
      <div className={styles.resultHead}>
        {applicationId !== null ? <code>{applicationId}</code> : <span>{t.notCreated}</span>}
        <LevelBadge level={asLevel(item.level)} />
      </div>
      {item.action !== null ? <p className={styles.action}>{titleOf(actions, item.action)}</p> : null}
      {error !== null ? <InlineError message={error} /> : null}
      {applicationId !== null ? (
        <div className={styles.links}>
          <button
            type="button"
            className={styles.linkButton}
            onClick={() => {
              onOpenApplication(applicationId);
            }}
          >
            {t.openInConveyor}
          </button>
          {item.in_borrower_app ? (
            <Link to={`/borrower?application=${applicationId}`} className={styles.link}>
              {t.openInApp}
              <IconForward size={16} aria-hidden />
            </Link>
          ) : null}
          {decisionId !== null ? (
            <Link to={`/decisions/${decisionId}`} className={styles.link}>
              <IconDecision size={16} aria-hidden />
              {t.openDecision}
            </Link>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

interface ScenarioCardProps {
  scenario: Scenario;
  run: ScenarioRun | undefined;
  onOpenApplication: (applicationId: string) => void;
}

function ScenarioCard({ scenario, run, onOpenApplication }: ScenarioCardProps) {
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: runScenario,
    onSuccess: (created) => {
      queryClient.setQueryData<ScenarioRun[]>(scenarioKeys.runs, (runs) => [created, ...(runs ?? [])]);
    },
    // Сценарий мог создать часть заявок и упасть на следующей: списки обновляем в любом случае.
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      await queryClient.invalidateQueries({ queryKey: borrowerKeys.applications });
      await queryClient.invalidateQueries({ queryKey: scenarioKeys.runs });
    },
  });
  const zone = scenario.zone === null ? CONTROL_ZONE : String(scenario.zone);
  return (
    <article className={styles.scenario}>
      <header className={styles.head}>
        <Badge tone="neutral">{label(t.zones, zone)}</Badge>
        <h3 className={styles.title}>{scenario.title}</h3>
        <p className={styles.summary}>{scenario.summary}</p>
      </header>
      <div className={styles.expected}>
        <p className={styles.expectedLabel}>{t.expected}</p>
        <p>{scenario.expected_summary}</p>
        <p className={styles.meta}>
          {t.applications}: <span className="num">{scenario.applications}</span>
        </p>
      </div>
      <Button
        variant={run === undefined ? "primary" : "secondary"}
        wide
        pending={start.isPending}
        onClick={() => {
          start.mutate(scenario.code);
        }}
      >
        {run === undefined ? t.run : t.runAgain}
      </Button>
      {start.isError ? <InlineError message={errorMessage(start.error)} /> : null}
      {run !== undefined ? (
        <section className={styles.run} aria-label={`${t.lastRun}${String(run.number)}`}>
          <p className={styles.meta}>
            {t.lastRun}
            {run.number} · {formatTime(run.created_at)}
          </p>
          <ul className={styles.results}>
            {run.applications.map((item, index) => (
              <RunResult
                key={item.application_id ?? `${item.person}-${String(index)}`}
                item={item}
                onOpenApplication={onOpenApplication}
              />
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

export function ScenarioPicker({
  onOpenApplication,
}: {
  onOpenApplication: (applicationId: string) => void;
}) {
  const scenarios = useScenarios();
  const runs = useScenarioRuns();
  return (
    <Card title={t.title} subtitle={t.subtitle}>
      {scenarios.isPending ? (
        <Skeleton rows={6} label={t.loading} />
      ) : scenarios.isError ? (
        <StateMessage
          tone="error"
          title={ru.errors.loadFailed}
          description={errorMessage(scenarios.error)}
          action={
            <Button
              onClick={() => {
                void scenarios.refetch();
              }}
            >
              {ru.common.retry}
            </Button>
          }
        />
      ) : scenarios.data.length === 0 ? (
        <StateMessage title={t.empty} />
      ) : (
        <div className={styles.list}>
          {scenarios.data.map((scenario) => (
            <ScenarioCard
              key={scenario.code}
              scenario={scenario}
              run={latestRun(runs.data ?? [], scenario.code)}
              onOpenApplication={onOpenApplication}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
