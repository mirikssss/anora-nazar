// Проверка целостности журнала против якоря и постановка контрольной точки.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { auditKeys, createCheckpoint, verifyAudit, type Verification } from "@/entities/audit";
import { hasPermission, useSession } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { IconShield } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { formatNumber, shortHash } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { InlineError } from "@/shared/ui/InlineError";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";

import styles from "./AuditVerify.module.css";

const t = ru.audit;

function verificationRows(result: Verification): SummaryRow[] {
  const rows: SummaryRow[] = [
    { key: "records", label: t.recordsChecked, value: formatNumber(result.records_checked) },
    { key: "checkpoints", label: t.checkpointsChecked, value: formatNumber(result.checkpoints_checked) },
  ];
  if (result.first_break !== null) {
    rows.push({
      key: "break",
      label: t.firstBreak,
      value: `№ ${String(result.first_break.seq)} · ${label(ru.auditKinds, result.first_break.kind)} · ${result.first_break.problem}`,
    });
  }
  if (result.anchor_mismatch !== null) {
    rows.push({
      key: "anchor",
      label: t.anchorMismatch,
      value: `№ ${String(result.anchor_mismatch.seq)} · ${result.anchor_mismatch.problem}`,
    });
  }
  return rows;
}

export function AuditVerify() {
  const session = useSession();
  const queryClient = useQueryClient();
  const verify = useMutation({ mutationFn: verifyAudit });
  const checkpoint = useMutation({
    mutationFn: createCheckpoint,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: auditKeys.records }),
  });
  const canVerify = hasPermission(session, PERMISSIONS.verifyAudit);
  const result = verify.data;
  const intact = result !== undefined && result.intact && result.anchor_mismatch === null;

  return (
    <Card title={t.verifyTitle}>
      <div className={styles.body}>
        <div className={styles.buttons}>
          <Button
            variant="primary"
            icon={IconShield}
            disabled={!canVerify}
            pending={verify.isPending}
            onClick={() => {
              verify.mutate();
            }}
          >
            {t.verify}
          </Button>
          <Button
            disabled={!canVerify}
            pending={checkpoint.isPending}
            onClick={() => {
              checkpoint.mutate();
            }}
          >
            {t.checkpoint}
          </Button>
        </div>
        {verify.isError ? <InlineError message={errorMessage(verify.error)} /> : null}
        {checkpoint.isError ? <InlineError message={errorMessage(checkpoint.error)} /> : null}
        {checkpoint.isSuccess ? (
          <p className={styles.note} role="status">
            {checkpoint.data === null
              ? t.checkpointNothing
              : `${t.checkpointDone} № ${String(checkpoint.data.seq)} · ${shortHash(checkpoint.data.merkle_root)} · ${checkpoint.data.anchored ? t.anchored : (checkpoint.data.anchor_error ?? t.notAnchored)}`}
          </p>
        ) : null}
        {result !== undefined ? (
          <div className={styles.result} role="status">
            <div className={styles.badges}>
              <Badge tone={intact ? "green" : "red"}>{intact ? t.intact : t.broken}</Badge>
              {!result.anchor_reachable ? <Badge tone="orange">{t.anchorUnreachable}</Badge> : null}
            </div>
            <SummaryList rows={verificationRows(result)} />
          </div>
        ) : null}
      </div>
    </Card>
  );
}
