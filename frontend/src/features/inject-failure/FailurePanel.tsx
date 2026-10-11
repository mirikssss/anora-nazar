// Кнопки сбоев имитатора банка: потерять итог, узел недоступен, очередь отстаёт, повтор с другой суммой.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import {
  operationKeys,
  repeatWithOtherAmount,
  setFailureFlags,
  useFailureFlags,
  useOperations,
  type FailureFlags,
} from "@/entities/operation";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatSum, parseInteger } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";
import { Switch } from "@/shared/ui/Switch";

import styles from "./FailurePanel.module.css";

const t = ru.failures;

const SWITCHES: readonly { key: keyof FailureFlags; label: string; hint: string }[] = [
  { key: "lose_outcome", label: t.loseOutcome, hint: t.loseOutcomeHint },
  { key: "node_unavailable", label: t.nodeUnavailable, hint: t.nodeUnavailableHint },
  { key: "queue_lag", label: t.queueLag, hint: t.queueLagHint },
];

function nodeMessage(response: Record<string, unknown>): string | null {
  const error = response.error;
  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return error.message;
  }
  return null;
}

function RepeatForm() {
  const operations = useOperations();
  const [operationKey, setOperationKey] = useState("");
  const [amount, setAmount] = useState("");
  const repeat = useMutation({
    mutationFn: ({ key, value }: { key: string; value: number }) => repeatWithOtherAmount(key, value),
  });
  const parsed = parseInteger(amount);
  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (operationKey !== "" && parsed !== null) repeat.mutate({ key: operationKey, value: parsed });
  };
  const result = repeat.data;
  return (
    <form className={styles.repeat} noValidate onSubmit={onSubmit}>
      <div>
        <p className={styles.label}>{t.repeatTitle}</p>
        <p className={styles.hint}>{t.repeatHint}</p>
      </div>
      <SelectField
        label={t.repeatOperation}
        value={operationKey}
        placeholder={ru.coreBanking.select}
        options={(operations.data ?? []).map((op) => ({ value: op.operation_key, label: op.operation_key }))}
        onChange={(event) => {
          setOperationKey(event.target.value);
        }}
      />
      <TextField
        label={t.repeatAmount}
        value={amount}
        inputMode="numeric"
        hint={parsed !== null ? formatSum(parsed) : undefined}
        onChange={(event) => {
          setAmount(event.target.value);
        }}
      />
      <Button type="submit" pending={repeat.isPending} disabled={operationKey === "" || parsed === null}>
        {t.repeatRun}
      </Button>
      {repeat.isError ? <InlineError message={errorMessage(repeat.error)} /> : null}
      {result !== undefined ? (
        <div className={styles.answer} role="status">
          <span>{t.nodeAnswered}</span>
          <Badge tone={result.node_status_code < 300 ? "green" : "red"}>
            {String(result.node_status_code)}
          </Badge>
          <span>{nodeMessage(result.node_response) ?? ru.common.none}</span>
        </div>
      ) : null}
    </form>
  );
}

export function FailurePanel() {
  const queryClient = useQueryClient();
  const flags = useFailureFlags();
  const update = useMutation({
    mutationFn: setFailureFlags,
    onSuccess: (next) => {
      queryClient.setQueryData(operationKeys.failures, next);
    },
  });
  return (
    <Card title={t.title} subtitle={t.subtitle} actions={<Badge tone="outline">{ru.common.simulator}</Badge>}>
      <div className={styles.body}>
        {flags.isPending ? (
          <Skeleton rows={3} label={ru.common.loading} />
        ) : flags.isError ? (
          <InlineError message={errorMessage(flags.error)} />
        ) : (
          <div className={styles.switches}>
            {SWITCHES.map((item) => (
              <Switch
                key={item.key}
                label={item.label}
                description={item.hint}
                checked={flags.data[item.key]}
                disabled={update.isPending}
                onChange={(checked) => {
                  update.mutate({ [item.key]: checked });
                }}
              />
            ))}
          </div>
        )}
        {update.isError ? <InlineError message={errorMessage(update.error)} /> : null}
        <RepeatForm />
      </div>
    </Card>
  );
}
