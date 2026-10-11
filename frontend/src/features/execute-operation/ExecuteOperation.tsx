// АБС исполняет операцию: запрос разрешения узла прямо перед проводкой, затем проводка и итог.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { applicationKeys, useApplications } from "@/entities/application";
import { executeOperation, operationKeys, type Operation, type OperationType } from "@/entities/operation";
import { useActs } from "@/entities/program";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatSum, parseInteger } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Choice } from "@/shared/ui/Choice";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./ExecuteOperation.module.css";

const t = ru.coreBanking;
const OPERATION_TYPES: readonly OperationType[] = ["disbursement", "supplier_payment"];
/** Оплата поставщику — только по акту приёмки этой заявки (Т5). */
const NEEDS_ACT: OperationType = "supplier_payment";

interface ExecuteOperationProps {
  initialApplicationId: string | null;
  /** Акт приёмки, по которому платить: форма сразу открывается на оплате поставщику. */
  initialActId: string | null;
  onExecuted: (operation: Operation) => void;
}

function ActField({
  applicationId,
  value,
  onChange,
}: {
  applicationId: string;
  value: string;
  onChange: (actId: string) => void;
}) {
  const acts = useActs(applicationId);
  const options = (acts.data ?? []).map((act) => ({
    value: act.act_id,
    label: `${act.act_id} · ${formatSum(act.invoice_amount)}`,
  }));
  return (
    <SelectField
      label={ru.borrower.acts.act}
      value={value}
      placeholder={ru.borrower.acts.actPlaceholder}
      options={options}
      hint={acts.isSuccess && options.length === 0 ? ru.borrower.acts.noActs : undefined}
      error={acts.isError ? errorMessage(acts.error) : undefined}
      onChange={(event) => {
        onChange(event.target.value);
      }}
    />
  );
}

export function ExecuteOperation({ initialApplicationId, initialActId, onExecuted }: ExecuteOperationProps) {
  const queryClient = useQueryClient();
  const applications = useApplications();
  const [applicationId, setApplicationId] = useState(initialApplicationId ?? "");
  const [operationType, setOperationType] = useState<OperationType>(
    initialActId === null ? "disbursement" : NEEDS_ACT,
  );
  const [actId, setActId] = useState(initialActId ?? "");
  const [tranche, setTranche] = useState("1");
  const execute = useMutation({
    mutationFn: executeOperation,
    onSuccess: onExecuted,
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: operationKeys.all });
      await queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    },
  });
  const options = (applications.data ?? [])
    .filter((app) => app.status !== "cancelled")
    .map((app) => ({ value: app.id, label: `${app.id} · ${label(ru.channels, app.channel)}` }));
  const trancheNumber = parseInteger(tranche);
  const needsAct = operationType === NEEDS_ACT;
  const ready = applicationId !== "" && trancheNumber !== null && (!needsAct || actId !== "");

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!ready) return;
    execute.mutate({
      application_id: applicationId,
      operation_type: operationType,
      tranche: trancheNumber,
      acceptance_act_id: needsAct ? actId : null,
    });
  };

  return (
    <Card title={t.executeTitle} subtitle={t.executeSubtitle}>
      <form className={styles.form} noValidate onSubmit={onSubmit}>
        <SelectField
          label={t.application}
          value={applicationId}
          placeholder={t.applicationPlaceholder}
          options={options}
          hint={applications.isSuccess && options.length === 0 ? t.noApplications : undefined}
          onChange={(event) => {
            setApplicationId(event.target.value);
            setActId("");
          }}
        />
        <Choice
          label={t.operationType}
          value={operationType}
          options={OPERATION_TYPES.map((value) => ({ value, label: label(ru.operationTypes, value) }))}
          onChange={setOperationType}
        />
        {needsAct && applicationId !== "" ? (
          <ActField applicationId={applicationId} value={actId} onChange={setActId} />
        ) : null}
        <TextField
          label={t.tranche}
          value={tranche}
          inputMode="numeric"
          error={trancheNumber === null ? ru.conveyor.notNumber : undefined}
          onChange={(event) => {
            setTranche(event.target.value);
          }}
        />
        {execute.isError ? <InlineError message={errorMessage(execute.error)} /> : null}
        <Button type="submit" variant="primary" wide pending={execute.isPending} disabled={!ready}>
          {t.execute}
        </Button>
      </form>
    </Card>
  );
}
