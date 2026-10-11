// Рабочее место аналитика (Блок 5): очередь, заявка, действие. На десктопе очередь и правая колонка
// стоят на месте и прокручиваются сами, меняется центр; на телефоне — очередь, затем дело с возвратом.
import { useState } from "react";
import { Link } from "react-router";

import { useCase, type CaseDetail } from "@/entities/case";
import { ApiError, errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";

import styles from "./AnalystWorkspace.module.css";
import { CaseSummary, type PiiState } from "./CaseSummary";
import { CaseWork } from "./CaseWork";
import { QUEUE_PATH } from "./model";
import { QueueColumn } from "./QueueColumn";

const t = ru.analyst;

function CaseColumns({ detail, pii }: { detail: CaseDetail; pii: PiiState }) {
  return (
    <>
      <div className={styles.main}>
        <CaseSummary detail={detail} pii={pii} />
      </div>
      <aside className={styles.side} aria-label={t.callAndOutcome}>
        <CaseWork detail={detail} />
      </aside>
    </>
  );
}

/** Полные ПДн запрашиваются отдельным компонентом: запрос с full_pii=true уходит только после нажатия. */
function FullPiiCase({ caseId, masked }: { caseId: string; masked: CaseDetail }) {
  const full = useCase(caseId, true);
  const pii: PiiState = {
    revealed: true,
    pending: full.isPending,
    error: full.isError ? full.error : null,
    onReveal: () => void full.refetch(),
  };
  return <CaseColumns detail={full.data ?? masked} pii={pii} />;
}

function CaseArea({ caseId }: { caseId: string }) {
  const [revealed, setRevealed] = useState(false);
  const masked = useCase(caseId);

  if (masked.isPending) {
    return (
      <>
        <div className={styles.main}>
          <Skeleton rows={8} label={t.caseLoading} />
        </div>
        <div className={styles.side}>
          <Skeleton rows={5} label={t.caseLoading} />
        </div>
      </>
    );
  }
  if (masked.isError) {
    const missing = masked.error instanceof ApiError && masked.error.status === 404;
    return (
      <div className={styles.placeholder}>
        {missing ? (
          <StateMessage title={t.caseNotFound} />
        ) : (
          <StateMessage
            tone="error"
            title={ru.errors.loadFailed}
            description={errorMessage(masked.error)}
            action={
              <Button size="sm" onClick={() => void masked.refetch()}>
                {ru.common.retry}
              </Button>
            }
          />
        )}
      </div>
    );
  }
  if (revealed) return <FullPiiCase caseId={caseId} masked={masked.data} />;
  return (
    <CaseColumns
      detail={masked.data}
      pii={{
        revealed: false,
        pending: false,
        error: null,
        onReveal: () => {
          setRevealed(true);
        },
      }}
    />
  );
}

export function AnalystWorkspace({ caseId }: { caseId: string | null }) {
  return (
    <div className={[styles.workspace, caseId !== null ? styles.withCase : ""].join(" ")}>
      {caseId !== null ? (
        <Link to={QUEUE_PATH} className={styles.back}>
          {t.backToQueue}
        </Link>
      ) : null}
      <div className={styles.queue}>
        <QueueColumn currentId={caseId} />
      </div>
      {caseId !== null ? (
        // Ключ по делу: раскрытие ПДн и черновик исхода не переносятся на соседнее дело.
        <CaseArea key={caseId} caseId={caseId} />
      ) : (
        <div className={styles.placeholder}>
          <StateMessage title={t.selectTitle} description={t.selectHint} />
        </div>
      )}
    </div>
  );
}
