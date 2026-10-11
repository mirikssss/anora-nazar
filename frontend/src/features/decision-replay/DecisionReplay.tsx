// Повтор решения на сохранённых входах и сравнение с другой версией модели — без побочных действий.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import {
  compareDecision,
  LevelBadge,
  parseResult,
  replayDecision,
  type DecisionResult,
} from "@/entities/decision";
import { useModelVersions } from "@/entities/model";
import { hasPermission, useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { IconRefresh } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { SelectField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./DecisionReplay.module.css";

const t = ru.decision;

function ResultLine({ title, result }: { title: string; result: DecisionResult }) {
  return (
    <div className={styles.line}>
      <span className={styles.lineTitle}>{title}</span>
      <LevelBadge level={result.level} compact />
      <span className={styles.codes}>
        {result.reasons.map((reason) => reason.code).join(", ") || ru.common.none}
      </span>
    </div>
  );
}

function Replay({ decisionId }: { decisionId: string }) {
  const replay = useMutation({ mutationFn: () => replayDecision(decisionId) });
  const data = replay.data;
  return (
    <section className={styles.block}>
      <p className={styles.hint}>{t.replayHint}</p>
      <Button
        icon={IconRefresh}
        pending={replay.isPending}
        onClick={() => {
          replay.mutate();
        }}
      >
        {t.replay}
      </Button>
      {replay.isError ? <InlineError message={errorMessage(replay.error)} /> : null}
      {data !== undefined ? (
        <div className={styles.result} role="status">
          <div className={styles.badges}>
            <Badge tone={data.identical ? "green" : "red"}>
              {data.identical ? t.replayIdentical : t.replayDifferent}
            </Badge>
            {!data.policy_unchanged ? <Badge tone="orange">{t.policyChanged}</Badge> : null}
          </div>
          {!data.identical ? (
            <>
              <ResultLine title={t.stored} result={parseResult(data.stored)} />
              <ResultLine title={t.replayed} result={parseResult(data.replayed)} />
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Compare({ decisionId }: { decisionId: string }) {
  const models = useModelVersions(true);
  const [modelId, setModelId] = useState("");
  const compare = useMutation({ mutationFn: (id: string) => compareDecision(decisionId, [id]) });
  const data = compare.data;
  if (models.isSuccess && models.data.length === 0) return null;
  return (
    <section className={styles.block}>
      <div>
        <p className={styles.blockTitle}>{t.compare}</p>
        <p className={styles.hint}>{t.compareHint}</p>
      </div>
      <SelectField
        label={t.compareModel}
        value={modelId}
        placeholder={ru.common.loading}
        options={(models.data ?? []).map((model) => ({
          value: model.model_version_id,
          label: `${model.name} · ${model.typology} · ${model.status}`,
        }))}
        onChange={(event) => {
          setModelId(event.target.value);
        }}
      />
      <Button
        pending={compare.isPending}
        disabled={modelId === ""}
        onClick={() => {
          compare.mutate(modelId);
        }}
      >
        {t.compareRun}
      </Button>
      {compare.isError ? <InlineError message={errorMessage(compare.error)} /> : null}
      {data !== undefined ? (
        <div className={styles.result} role="status">
          <Badge tone={data.level_changed ? "orange" : "neutral"}>
            {data.level_changed ? t.levelChanged : t.levelSame}
          </Badge>
          <ResultLine title={t.stored} result={parseResult(data.stored)} />
          <ResultLine title={t.compared} result={parseResult(data.compared)} />
        </div>
      ) : null}
    </section>
  );
}

export function DecisionReplay({ decisionId }: { decisionId: string }) {
  const session = useSession();
  return (
    <Card title={t.replayTitle}>
      <div className={styles.body}>
        <Replay decisionId={decisionId} />
        {hasPermission(session, PERMISSIONS.viewQuality) ? <Compare decisionId={decisionId} /> : null}
      </div>
    </Card>
  );
}
