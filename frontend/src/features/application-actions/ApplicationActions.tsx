// Действия конвейера с заявкой: новая версия условий, повторная оценка, отмена.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import {
  applicationKeys,
  cancelApplication,
  changeApplication,
  reassessApplication,
  snapshotView,
  type Application,
  type ApplicationChange,
} from "@/entities/application";
import { ApiError, errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatSum, parseInteger } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Dialog } from "@/shared/ui/Dialog";
import { TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./ApplicationActions.module.css";

const t = ru.application;

function parseOptional(value: string): number | null | "invalid" {
  return value.trim() === "" ? null : (parseInteger(value) ?? "invalid");
}

function ChangeDialog({ application, onClose }: { application: Application; onClose: () => void }) {
  const view = snapshotView(application);
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState(view.amount !== null ? String(view.amount) : "");
  const [term, setTerm] = useState(view.termMonths !== null ? String(view.termMonths) : "");
  const [account, setAccount] = useState(view.account ?? "");
  const [localError, setLocalError] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: (patch: ApplicationChange) => changeApplication(application.id, patch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      onClose();
    },
  });

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextAmount = parseOptional(amount);
    const nextTerm = parseOptional(term);
    if (nextAmount === "invalid" || nextTerm === "invalid") {
      setLocalError(ru.conveyor.notNumber);
      return;
    }
    const patch: ApplicationChange = {};
    if (nextAmount !== null && nextAmount !== view.amount) patch.amount = nextAmount;
    if (nextTerm !== null && nextTerm !== view.termMonths) patch.term_months = nextTerm;
    if (application.channel === "online" && account.trim() !== "" && account.trim() !== view.account) {
      patch.disbursement_account = account.trim();
    }
    setLocalError(Object.keys(patch).length === 0 ? t.changeNothing : null);
    if (Object.keys(patch).length > 0) change.mutate(patch);
  };
  const fields = change.error instanceof ApiError ? change.error.fields : {};
  const amountValue = parseOptional(amount);

  return (
    <Dialog open title={t.changeTitle} closeLabel={ru.common.close} onClose={onClose}>
      <form className={styles.form} noValidate onSubmit={onSubmit}>
        <p>{t.changeHint}</p>
        <TextField
          label={t.amount}
          value={amount}
          inputMode="numeric"
          hint={typeof amountValue === "number" ? formatSum(amountValue) : undefined}
          error={fields.amount}
          onChange={(event) => {
            setAmount(event.target.value);
          }}
        />
        <TextField
          label={t.term}
          value={term}
          inputMode="numeric"
          error={fields.term_months}
          onChange={(event) => {
            setTerm(event.target.value);
          }}
        />
        {application.channel === "online" ? (
          <TextField
            label={t.account}
            value={account}
            error={fields.disbursement_account}
            onChange={(event) => {
              setAccount(event.target.value);
            }}
          />
        ) : null}
        {localError !== null ? <InlineError message={localError} /> : null}
        {change.isError ? <InlineError message={errorMessage(change.error)} /> : null}
        <div className={styles.footer}>
          <Button onClick={onClose}>{ru.common.cancel}</Button>
          <Button type="submit" variant="primary" pending={change.isPending}>
            {t.changeSubmit}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ApplicationActions({ application }: { application: Application }) {
  const queryClient = useQueryClient();
  const [changing, setChanging] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: applicationKeys.all });
  const reassess = useMutation({ mutationFn: () => reassessApplication(application.id), onSettled: refresh });
  const cancel = useMutation({ mutationFn: () => cancelApplication(application.id), onSettled: refresh });
  const cancelled = application.status === "cancelled";
  const error = reassess.error ?? cancel.error;

  return (
    <div className={styles.actions}>
      <div className={styles.buttons}>
        <Button
          size="sm"
          disabled={cancelled}
          onClick={() => {
            setChanging(true);
          }}
        >
          {t.change}
        </Button>
        <Button
          size="sm"
          disabled={cancelled}
          pending={reassess.isPending}
          onClick={() => {
            reassess.mutate();
          }}
        >
          {t.reassess}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={cancelled}
          pending={cancel.isPending}
          onClick={() => {
            cancel.mutate();
          }}
        >
          {t.cancel}
        </Button>
      </div>
      {error !== null ? <InlineError message={errorMessage(error)} /> : null}
      {changing ? (
        <ChangeDialog
          application={application}
          onClose={() => {
            setChanging(false);
          }}
        />
      ) : null}
    </div>
  );
}
