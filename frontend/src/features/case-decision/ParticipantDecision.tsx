// Решение по одной заявке дела: удержать, отпустить или отказать — со своим основанием и, по праву,
// ролью участника. Групповой флаг основанием не предлагается (Блок 4): основание — факты этой заявки.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  caseKeys,
  decideApplication,
  type CaseApplication,
  type CaseDetail,
  type ParticipantDecision as DecisionBody,
} from "@/entities/case";
import { hasPermission, useSession } from "@/entities/session";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { PERMISSIONS } from "@/shared/config/permissions";
import { DEMO, pick } from "@/shared/demo";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Choice } from "@/shared/ui/Choice";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";
import { SummaryList } from "@/shared/ui/SummaryList";

import styles from "./ParticipantDecision.module.css";

const t = ru.control.decision;

type Action = DecisionBody["action"];
const ACTIONS: readonly string[] = ["hold", "release", "refuse"] satisfies Action[];
/** Удержание и его снятие — отдельное право; отказ — право решения по делу. */
const HOLD_ACTIONS: readonly Action[] = ["hold", "release"];

function isAction(code: string): code is Action {
  return ACTIONS.includes(code);
}

interface ParticipantDecisionProps {
  detail: CaseDetail;
  application: CaseApplication;
}

function CurrentDecision({ application }: { application: CaseApplication }) {
  const texts = useStaffTexts().data;
  if (application.decision === null) return null;
  return (
    <div className={styles.current}>
      <h4 className={styles.subheading}>{t.current}</h4>
      <SummaryList
        rows={[
          {
            key: "action",
            label: t.action,
            value: titleOf(texts?.participant_actions, application.decision),
          },
          {
            key: "role",
            label: t.role,
            value:
              application.role === null
                ? ru.common.none
                : titleOf(texts?.participant_roles, application.role),
          },
          { key: "basis", label: t.basis, value: application.basis ?? ru.common.none },
          {
            key: "by",
            label: t.by,
            value: [application.decided_by, application.decided_at && formatDateTime(application.decided_at)]
              .filter(Boolean)
              .join(" · "),
          },
        ]}
      />
    </div>
  );
}

export function ParticipantDecision({ detail, application }: ParticipantDecisionProps) {
  const texts = useStaffTexts().data;
  const session = useSession();
  const queryClient = useQueryClient();
  const canDecide = hasPermission(session, PERMISSIONS.decideGroupCases);
  const canManageHolds = hasPermission(session, PERMISSIONS.manageHolds);
  const canAssignRole = hasPermission(session, PERMISSIONS.assignParticipantRoles);
  const [action, setAction] = useState<Action | null>(null);
  const [role, setRole] = useState("");
  const [basis, setBasis] = useState("");
  const [basisExample] = useState(() => pick(DEMO.notes));
  const [touched, setTouched] = useState(false);
  const save = useMutation({
    mutationFn: (body: DecisionBody) => decideApplication(detail.case_id, application.application_id, body),
    onSuccess: async () => {
      setAction(null);
      setRole("");
      setBasis("");
      setTouched(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: caseKeys.detail(detail.case_id) }),
        queryClient.invalidateQueries({ queryKey: caseKeys.graph(detail.case_id) }),
      ]);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: caseKeys.queues }),
  });

  const actions = detail.participant_actions
    .filter(isAction)
    .filter((code) => canManageHolds || !HOLD_ACTIONS.includes(code));
  const basisMissing = basis.trim() === "";
  const submit = () => {
    setTouched(true);
    if (action === null || basisMissing) return;
    save.mutate({ action, role: role === "" ? null : role, basis: basis.trim() });
  };

  const notice =
    detail.status === "closed" ? t.closed : !canDecide || actions.length === 0 ? t.readOnly : null;

  return (
    <section className={styles.decision} aria-label={t.title}>
      <h3 className={styles.heading}>{t.title}</h3>
      <CurrentDecision application={application} />
      {notice !== null ? (
        <p className={styles.hint}>{notice}</p>
      ) : (
        <>
          <Choice
            label={t.action}
            value={action}
            options={actions.map((code) => ({
              value: code,
              label: titleOf(texts?.participant_actions, code),
            }))}
            error={touched && action === null ? t.chooseAction : undefined}
            onChange={setAction}
          />
          {action === "refuse" ? <p className={styles.hint}>{t.refuseHint}</p> : null}
          {canAssignRole ? (
            <SelectField
              label={t.role}
              value={role}
              options={[
                { value: "", label: t.roleNone },
                ...detail.participant_roles.map((code) => ({
                  value: code,
                  label: titleOf(texts?.participant_roles, code),
                })),
              ]}
              onChange={(event) => {
                setRole(event.target.value);
              }}
            />
          ) : (
            <p className={styles.hint}>{t.noRoleRight}</p>
          )}
          <TextField
            label={t.basis}
            hint={t.basisHint}
            value={basis}
            error={touched && basisMissing ? t.basisRequired : undefined}
            suggestion={{
              value: basisExample,
              onAccept: () => {
                setBasis(basisExample);
              },
            }}
            onChange={(event) => {
              setBasis(event.target.value);
            }}
          />
          {save.isError ? <InlineError message={errorMessage(save.error)} /> : null}
          <Button variant="primary" wide pending={save.isPending} onClick={submit}>
            {t.submit}
          </Button>
        </>
      )}
    </section>
  );
}
