// Заявка заёмщика в приложении: только сумма и срок — остальное банк знает о своём клиенте.
import { useState, type SubmitEvent } from "react";

import { submitBorrowerApplication, useBorrowerAction, type BorrowerApplication } from "@/entities/borrower";
import { ApiError, errorMessage } from "@/shared/api";
import { DEMO, pick, stepBetween } from "@/shared/demo";
import { ru } from "@/shared/i18n/ru";
import { formatSum, parseInteger } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./BorrowerApplyForm.module.css";

const t = ru.borrower;

type Key = "amount" | "termMonths";
type Values = Record<Key, string>;
const FIELD_PATHS: Readonly<Record<string, Key>> = { amount: "amount", term_months: "termMonths" };

function makeExample(): Values {
  const { amount, termMonths } = DEMO.online;
  return {
    amount: String(stepBetween(amount.min, amount.max, amount.step)),
    termMonths: String(pick(termMonths)),
  };
}

function check(values: Values): Partial<Values> {
  const errors: Partial<Values> = {};
  for (const key of ["amount", "termMonths"] as const) {
    if (values[key].trim() === "") errors[key] = t.required;
    else if (parseInteger(values[key]) === null) errors[key] = t.notNumber;
  }
  return errors;
}

interface BorrowerApplyFormProps {
  personaCode: string;
  onSubmitted: (application: BorrowerApplication) => void;
}

export function BorrowerApplyForm({ personaCode, onSubmitted }: BorrowerApplyFormProps) {
  const [values, setValues] = useState<Values>({ amount: "", termMonths: "" });
  const [errors, setErrors] = useState<Partial<Values>>({});
  const [example, setExample] = useState(makeExample);
  const submit = useBorrowerAction(submitBorrowerApplication);

  const set = (key: Key, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
  };
  const serverErrors: Partial<Values> = {};
  if (submit.error instanceof ApiError) {
    for (const [path, message] of Object.entries(submit.error.fields)) {
      const key = FIELD_PATHS[path];
      if (key !== undefined) serverErrors[key] = message;
    }
  }
  const shown = { ...serverErrors, ...errors };
  const amount = parseInteger(values.amount);

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = check(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    submit.mutate(
      {
        persona_code: personaCode,
        amount: parseInteger(values.amount) ?? 0,
        term_months: parseInteger(values.termMonths) ?? 0,
      },
      {
        onSuccess: (application) => {
          setExample(makeExample());
          onSubmitted(application);
        },
      },
    );
  };

  const field = (key: Key, label: string, hint?: string) => (
    <TextField
      label={label}
      value={values[key]}
      inputMode="numeric"
      className={styles.input}
      hint={hint}
      error={shown[key]}
      suggestion={{
        value: example[key],
        onAccept: () => {
          set(key, example[key]);
        },
      }}
      onChange={(event) => {
        set(key, event.target.value);
      }}
    />
  );

  return (
    <form className={styles.form} noValidate onSubmit={onSubmit}>
      {field("amount", t.amount, amount !== null && amount > 0 ? formatSum(amount) : undefined)}
      {field("termMonths", t.term)}
      {submit.isError && Object.keys(serverErrors).length === 0 ? (
        <InlineError message={errorMessage(submit.error)} />
      ) : null}
      <Button type="submit" variant="primary" wide pending={submit.isPending}>
        {t.apply}
      </Button>
    </form>
  );
}
