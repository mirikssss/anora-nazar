// Предложение изменить порог: выбор порога, новое значение и обоснование. В силу вступает только после
// подтверждения другим сотрудником (Блок 4).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import {
  formatThreshold,
  parseThreshold,
  policyKeys,
  proposeChange,
  thresholdTitle,
  type Threshold,
} from "@/entities/policy";
import { ApiError, errorMessage } from "@/shared/api";
import { pick } from "@/shared/demo";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import { exampleReason, exampleValue } from "./example";
import styles from "./ThresholdChange.module.css";

const t = ru.risk.policy;

interface FormState {
  path: string;
  value: string;
  reason: string;
}

type FormErrors = Partial<Record<keyof FormState, string>>;

const EMPTY: FormState = { path: "", value: "", reason: "" };

const TOGGLE = { on: "true", off: "false" } as const;

function isToggle(threshold: Threshold | undefined): boolean {
  return typeof threshold?.value === "boolean";
}

/** Новое значение из формы: у переключателя — выбор «включить/выключить», у порога — число. */
function parseValue(input: string, current: Threshold | undefined): Threshold["value"] | null {
  if (!isToggle(current)) return parseThreshold(input);
  if (input === TOGGLE.on) return true;
  if (input === TOGGLE.off) return false;
  return null;
}

function validate(state: FormState, current: Threshold | undefined): FormErrors {
  const errors: FormErrors = {};
  const value = parseValue(state.value, current);
  if (current === undefined) errors.path = t.errors.threshold;
  if (value === null) errors.value = isToggle(current) ? t.errors.toggle : t.errors.value;
  else if (current !== undefined && value === current.value) errors.value = t.errors.same;
  if (state.reason.trim() === "") errors.reason = t.errors.reason;
  return errors;
}

export function ThresholdChange({ thresholds }: { thresholds: readonly Threshold[] }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [valueExample, setValueExample] = useState<string | null>(null);
  const [reasonExample, setReasonExample] = useState(exampleReason);
  const current = thresholds.find((threshold) => threshold.path === state.path);

  const propose = useMutation({
    mutationFn: proposeChange,
    onSuccess: async () => {
      setState(EMPTY);
      setValueExample(null);
      setReasonExample(exampleReason());
      await queryClient.invalidateQueries({ queryKey: policyKeys.overview });
    },
  });
  const fieldErrors = propose.error instanceof ApiError ? propose.error.fields : {};

  const update = (patch: Partial<FormState>) => {
    setState((previous) => ({ ...previous, ...patch }));
    setErrors((previous) => Object.fromEntries(Object.entries(previous).filter(([key]) => !(key in patch))));
    propose.reset();
  };

  const choose = (path: string) => {
    const threshold = thresholds.find((item) => item.path === path);
    setValueExample(threshold === undefined ? null : exampleValue(threshold.value));
    update({ path, value: "" });
  };

  /** Каждое нажатие — другой порог, значение и обоснование. */
  const fillExample = () => {
    if (thresholds.length === 0) return;
    const threshold = pick(thresholds);
    const value = exampleValue(threshold.value);
    const reason = exampleReason();
    setValueExample(value);
    setReasonExample(reason);
    update({ path: threshold.path, value, reason });
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = validate(state, current);
    setErrors(found);
    const value = parseValue(state.value, current);
    if (Object.keys(found).length > 0 || current === undefined || value === null) return;
    propose.mutate({ changes: { [current.path]: value }, reason: state.reason.trim() });
  };

  return (
    <Card
      title={t.proposeTitle}
      subtitle={t.proposeSubtitle}
      actions={
        <Button size="sm" variant="ghost" onClick={fillExample}>
          {ru.field.fillExample}
        </Button>
      }
    >
      <form className={styles.form} noValidate onSubmit={onSubmit}>
        <SelectField
          label={t.threshold}
          value={state.path}
          placeholder={t.choosePlaceholder}
          options={thresholds.map((threshold) => ({
            value: threshold.path,
            label: thresholdTitle(threshold.path),
          }))}
          hint={current === undefined ? undefined : `${t.current}: ${formatThreshold(current.value)}`}
          error={errors.path}
          onChange={(event) => {
            choose(event.target.value);
          }}
        />
        {isToggle(current) ? (
          <SelectField
            label={t.newValue}
            value={state.value}
            placeholder={t.chooseState}
            options={[
              { value: TOGGLE.on, label: t.turnOn },
              { value: TOGGLE.off, label: t.turnOff },
            ]}
            error={errors.value ?? fieldErrors[`changes.${state.path}`]}
            onChange={(event) => {
              update({ value: event.target.value });
            }}
          />
        ) : (
          <TextField
            label={t.newValue}
            value={state.value}
            inputMode="decimal"
            autoComplete="off"
            disabled={current === undefined}
            error={errors.value ?? fieldErrors[`changes.${state.path}`]}
            suggestion={
              valueExample === null
                ? undefined
                : {
                    value: valueExample,
                    onAccept: () => {
                      update({ value: valueExample });
                    },
                  }
            }
            onChange={(event) => {
              update({ value: event.target.value });
            }}
          />
        )}
        <TextField
          label={t.reason}
          value={state.reason}
          hint={t.reasonHint}
          autoComplete="off"
          error={errors.reason ?? fieldErrors.reason}
          suggestion={{
            value: reasonExample,
            onAccept: () => {
              update({ reason: reasonExample });
            },
          }}
          onChange={(event) => {
            update({ reason: event.target.value });
          }}
        />
        {propose.isError ? <InlineError message={errorMessage(propose.error)} /> : null}
        {propose.isSuccess ? <p className={styles.done}>{t.proposed}</p> : null}
        <div className={styles.actions}>
          <Button type="submit" variant="primary" pending={propose.isPending}>
            {t.submit}
          </Button>
        </div>
      </form>
    </Card>
  );
}
