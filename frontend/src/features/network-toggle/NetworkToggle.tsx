// Предложение включить или выключить сеть кредиторов: тот же порог политики со вторым подписантом
// (`toggle_path` из обзора сети), только с одним полем — обоснованием.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { networkKeys } from "@/entities/network";
import { policyKeys, proposeChange } from "@/entities/policy";
import { ApiError, errorMessage } from "@/shared/api";
import { DEMO, pick } from "@/shared/demo";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./NetworkToggle.module.css";

const t = ru.risk.network;

function exampleReason(turnOn: boolean): string {
  return pick(turnOn ? DEMO.networkReasons.on : DEMO.networkReasons.off);
}

interface NetworkToggleProps {
  enabled: boolean;
  togglePath: string;
}

export function NetworkToggle({ enabled, togglePath }: NetworkToggleProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | undefined>();
  // После отправки форма уходит: на её месте — предложение, ждущее второго подписанта.
  const [example] = useState(() => exampleReason(!enabled));
  const propose = useMutation({
    mutationFn: proposeChange,
    onSuccess: async () => {
      setOpen(false);
      setReason("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: policyKeys.overview }),
        queryClient.invalidateQueries({ queryKey: networkKeys.overview }),
      ]);
    },
  });
  const fieldError = propose.error instanceof ApiError ? propose.error.fields.reason : undefined;
  const action = enabled ? t.proposeOff : t.proposeOn;

  if (!open) {
    return (
      <Button
        size="sm"
        onClick={() => {
          setOpen(true);
        }}
      >
        {action}
      </Button>
    );
  }

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = reason.trim();
    if (text === "") {
      setError(t.reasonRequired);
      return;
    }
    propose.mutate({ changes: { [togglePath]: !enabled }, reason: text });
  };

  return (
    <form className={styles.form} noValidate onSubmit={onSubmit}>
      <TextField
        label={t.reason}
        value={reason}
        hint={t.reasonHint}
        autoComplete="off"
        error={error ?? fieldError}
        suggestion={{
          value: example,
          onAccept: () => {
            setReason(example);
            setError(undefined);
          },
        }}
        onChange={(event) => {
          setReason(event.target.value);
          setError(undefined);
          propose.reset();
        }}
      />
      {propose.isError && fieldError === undefined ? (
        <InlineError message={errorMessage(propose.error)} />
      ) : null}
      <div className={styles.actions}>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(false);
            propose.reset();
          }}
        >
          {ru.common.cancel}
        </Button>
        <Button type="submit" size="sm" variant="primary" pending={propose.isPending}>
          {action}
        </Button>
      </div>
    </form>
  );
}
