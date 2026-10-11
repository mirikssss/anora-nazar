// АБС исполняет операцию: запрос разрешения узла прямо перед проводкой, затем проводка и итог.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { applicationKeys, useApplications } from "@/entities/application";
import { executeOperation, operationKeys, type Operation, type OperationType } from "@/entities/operation";
import { errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { parseInteger } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Choice } from "@/shared/ui/Choice";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./ExecuteOperation.module.css";

const t = ru.coreBanking;
const OPERATION_TYPES: readonly OperationType[] = ["disbursement", "supplier_payment"];

interface ExecuteOperationProps {
  initialApplicationId: string | null;
  onExecuted: (operation: Operation) => void;
}

export function ExecuteOperation({ initialApplicationId, onExecuted }: ExecuteOperationProps) {
  const queryClient = useQueryClient();
  const applications = useApplications();
  const [applicationId, setApplicationId] = useState(initialApplicationId ?? "");
  const [operationType, setOperationType] = useState<OperationType>("disbursement");
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

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (applicationId === "" || trancheNumber === null) return;
    execute.mutate({ application_id: applicationId, operation_type: operationType, tranche: trancheNumber });
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
          }}
        />
        <Choice
          label={t.operationType}
          value={operationType}
          options={OPERATION_TYPES.map((value) => ({ value, label: label(ru.operationTypes, value) }))}
          onChange={setOperationType}
        />
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
        <Button
          type="submit"
          variant="primary"
          wide
          pending={execute.isPending}
          disabled={applicationId === "" || trancheNumber === null}
        >
          {t.execute}
        </Button>
      </form>
    </Card>
  );
}
