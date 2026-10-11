// Форма своей заявки с переключателем канала: онлайн-микрозаём или программный займ в филиале.
import { useState, type SubmitEvent } from "react";

import type { Application } from "@/entities/application";
import { useBranches } from "@/entities/branch";
import { useHelpers, useSuppliers } from "@/entities/program";
import { ApiError, errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatSum, parseInteger } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Choice } from "@/shared/ui/Choice";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./ApplicationForm.module.css";
import {
  EMPTY_FORM,
  FIELD_PATHS,
  serverErrors,
  SESSION_EVENTS,
  validate,
  type FormErrors,
  type FormState,
  type SelfBanChoice,
  type TextKey,
  unmappedMessages,
} from "./form";
import {
  exampleBranch,
  exampleHelper,
  exampleSupplier,
  exampleValue,
  helperMahalla,
  itemCategory,
  makeExample,
  type Example,
  type ExampleContext,
} from "./example";
import { useSubmitApplication } from "./useSubmitApplication";

const t = ru.conveyor;

function sumHint(value: string): string | undefined {
  const amount = parseInteger(value);
  return amount !== null && amount > 0 ? formatSum(amount) : undefined;
}

export function ApplicationForm({ onSubmitted }: { onSubmitted: (application: Application) => void }) {
  const [state, setState] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [example, setExample] = useState(makeExample);
  const branches = useBranches();
  const submit = useSubmitApplication((application) => {
    setErrors({});
    setExample(makeExample());
    onSubmitted(application);
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setState((current) => ({ ...current, [key]: value }));
  };
  const apiFields = submit.error instanceof ApiError ? serverErrors(submit.error.fields) : {};
  const shownErrors: FormErrors = { ...apiFields, ...errors };
  const unmapped = submit.error instanceof ApiError ? unmappedMessages(submit.error.fields) : [];

  const branchList = branches.data ?? [];
  const branch = branchList.find((item) => item.id === state.branchId);
  // Справочники платформы программ небольшие: грузятся целиком один раз и фильтруются по району доставки.
  const helpers = useHelpers(null);
  const suppliers = useSuppliers(null, null);
  const allHelpers = helpers.data ?? [];
  const allSuppliers = suppliers.data ?? [];
  const programDistricts = new Set(
    allHelpers
      .map((item) => item.district)
      .filter((name) => allSuppliers.some((item) => item.district === name)),
  );
  const exampleDistrict = exampleBranch(example, {
    channel: state.channel,
    branches: branchList,
    branch,
    helpers: [],
    suppliers: [],
    programDistricts,
  })?.district;
  const district = state.district.trim() || exampleDistrict || "";
  const category = itemCategory(state.itemCode, example);
  const context: ExampleContext = {
    channel: state.channel,
    branches: branchList,
    branch,
    helpers: allHelpers.filter((item) => item.district === district),
    suppliers: allSuppliers.filter((item) => item.district === district && item.category === category),
    programDistricts,
  };

  // Пример, из которого ещё не подставлены помощник и поставщик: справочники нового района были в пути.
  const [pendingFill, setPendingFill] = useState<Example | null>(null);
  // Подстановка при отрисовке, а не в эффекте (приём React «состояние из предыдущей отрисовки»):
  // как только справочники района пришли, пример дописывает помощника и поставщика один раз.
  if (pendingFill !== null) {
    const helper = exampleHelper(pendingFill, context.helpers);
    const supplier = exampleSupplier(pendingFill, context.suppliers);
    if (helper !== undefined && supplier !== undefined) {
      setPendingFill(null);
      setState((current) => ({
        ...current,
        helperId: current.helperId || helper.id,
        helperMahalla: current.helperMahalla || helperMahalla(helper),
        supplierInn: current.supplierInn || supplier.inn,
        supplierAccount: current.supplierAccount || supplier.account,
      }));
    }
  }

  const suggestion = (key: TextKey) => {
    const value = exampleValue(example, key, context);
    return value === ""
      ? undefined
      : {
          value,
          onAccept: () => {
            set(key, value);
          },
        };
  };
  /** Каждое нажатие — новый заявитель целиком; канал и итоги проверок остаются выбором проверяющего. */
  const fillExample = () => {
    const chosen = exampleBranch(example, context);
    const next: FormState = { ...state };
    for (const key of Object.values(FIELD_PATHS)) {
      next[key] = exampleValue(example, key, { ...context, branch: chosen });
    }
    setState(next);
    setErrors({});
    setPendingFill(next.helperId === "" || next.supplierInn === "" ? example : null);
    setExample(makeExample());
  };
  const chooseHelper = (helperId: string) => {
    const helper = context.helpers.find((item) => item.id === helperId);
    setState((current) => ({
      ...current,
      helperId,
      helperMahalla: helper === undefined ? "" : helperMahalla(helper),
    }));
  };
  const chooseSupplier = (inn: string) => {
    const supplier = context.suppliers.find((item) => item.inn === inn);
    setState((current) => ({ ...current, supplierInn: inn, supplierAccount: supplier?.account ?? "" }));
  };
  const directoryError = (query: { isError: boolean; error: unknown }) =>
    query.isError ? errorMessage(query.error) : undefined;
  const selectedSupplier = context.suppliers.find((item) => item.inn === state.supplierInn);

  const text = (
    key: TextKey,
    fieldLabel: string,
    placeholder?: string,
    extra?: { hint?: string | undefined; numeric?: boolean },
  ) => (
    <TextField
      label={fieldLabel}
      value={state[key]}
      placeholder={placeholder}
      suggestion={suggestion(key)}
      inputMode={extra?.numeric === true ? "numeric" : undefined}
      hint={extra?.hint}
      error={shownErrors[key]}
      onChange={(event) => {
        set(key, event.target.value);
      }}
    />
  );

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = validate(state);
    setErrors(found);
    if (Object.keys(found).length === 0) submit.mutate(state);
  };
  return (
    <Card
      title={t.formTitle}
      subtitle={t.formSubtitle}
      actions={
        <Button size="sm" variant="ghost" onClick={fillExample}>
          {ru.field.fillExample}
        </Button>
      }
    >
      <form className={styles.form} noValidate onSubmit={onSubmit}>
        <fieldset className={styles.section}>
          <legend className={styles.legend}>{t.sections.channel}</legend>
          <Choice
            label={ru.application.channel}
            value={state.channel}
            options={[
              { value: "online", label: label(ru.channels, "online") },
              { value: "program", label: label(ru.channels, "program") },
            ]}
            onChange={(value) => {
              set("channel", value);
            }}
          />
          <div className={styles.grid}>
            <SelectField
              label={ru.application.branch}
              value={state.branchId}
              placeholder={branches.isPending ? t.branchesLoading : t.branchPlaceholder}
              options={(branches.data ?? []).map((item) => ({
                value: item.id,
                label: `${item.name} · ${item.district}`,
              }))}
              error={shownErrors.branchId ?? (branches.isError ? errorMessage(branches.error) : undefined)}
              onChange={(event) => {
                // Другой филиал — другой район: помощник прежнего района к заявке не подходит.
                setState((current) => ({
                  ...current,
                  branchId: event.target.value,
                  employeeId: "",
                  helperId: "",
                  helperMahalla: "",
                }));
              }}
            />
            <SelectField
              label={ru.application.employee}
              value={state.employeeId}
              options={[
                { value: "", label: t.employeeNone },
                ...(branch?.employees ?? []).map((item) => ({ value: item.id, label: item.display_name })),
              ]}
              disabled={branch === undefined}
              error={shownErrors.employeeId}
              onChange={(event) => {
                set("employeeId", event.target.value);
              }}
            />
          </div>
        </fieldset>

        <fieldset className={styles.section}>
          <legend className={styles.legend}>{t.sections.applicant}</legend>
          <div className={styles.grid}>
            {text("pinfl", ru.application.pinfl, t.placeholders.pinfl, { numeric: true })}
            {text("phone", ru.application.phone, t.placeholders.phone, { numeric: true })}
            {text("deviceId", ru.application.device, t.placeholders.device)}
            {text("employerInn", t.labels.employerInn, t.placeholders.employerInn, { numeric: true })}
          </div>
          {text("address", t.labels.address, t.placeholders.address)}
          {text("registrationMahalla", t.labels.registrationMahalla, t.placeholders.registrationMahalla)}
        </fieldset>

        <fieldset className={styles.section}>
          <legend className={styles.legend}>{t.sections.loan}</legend>
          <div className={styles.grid}>
            {text("amount", ru.application.amount, t.placeholders.amount, {
              numeric: true,
              hint: sumHint(state.amount),
            })}
            {text("termMonths", ru.application.term, t.placeholders.term, { numeric: true })}
          </div>
          {text("purpose", ru.application.purpose, t.placeholders.purpose)}
          {state.channel === "online"
            ? text("account", ru.application.account, t.placeholders.account)
            : null}
        </fieldset>

        {state.channel === "program" ? (
          <fieldset className={styles.section}>
            <legend className={styles.legend}>{t.sections.program}</legend>
            <div className={styles.grid}>
              {text("district", ru.application.district, t.placeholders.district)}
              <SelectField
                label={ru.application.helper}
                value={state.helperId}
                placeholder={helpers.isPending ? t.directoryLoading : t.helperPlaceholder}
                options={context.helpers.map((item) => ({
                  value: item.id,
                  label: `${item.mahalla} · ${item.id}`,
                }))}
                hint={helpers.isSuccess && context.helpers.length === 0 ? t.directoryEmpty : undefined}
                error={shownErrors.helperId ?? directoryError(helpers)}
                onChange={(event) => {
                  chooseHelper(event.target.value);
                }}
              />
              <SelectField
                label={ru.application.supplier}
                value={state.supplierInn}
                placeholder={suppliers.isPending ? t.directoryLoading : t.supplierPlaceholder}
                options={context.suppliers.map((item) => ({
                  value: item.inn,
                  label: `${item.name} · ${item.inn}`,
                }))}
                hint={
                  selectedSupplier !== undefined
                    ? `${t.labels.supplierAccount}: ${selectedSupplier.account}`
                    : suppliers.isSuccess && context.suppliers.length === 0
                      ? t.directoryEmpty
                      : undefined
                }
                error={shownErrors.supplierInn ?? shownErrors.supplierAccount ?? directoryError(suppliers)}
                onChange={(event) => {
                  chooseSupplier(event.target.value);
                }}
              />
              {text("itemCode", ru.application.item, t.placeholders.item)}
              {text("unit", t.labels.unit, t.placeholders.unit)}
              {text("unitPrice", ru.application.unitPrice, t.placeholders.amount, {
                numeric: true,
                hint: sumHint(state.unitPrice),
              })}
              {text("quantity", ru.application.quantity, undefined, { numeric: true })}
            </div>
          </fieldset>
        ) : null}

        <fieldset className={styles.section}>
          <legend className={styles.legend}>{t.sections.checks}</legend>
          <p className={styles.hint}>{t.checksHint}</p>
          <Choice
            label={ru.application.biometry}
            value={state.biometry}
            options={[
              { value: "passed", label: label(ru.checks.biometry, "passed") },
              { value: "failed", label: label(ru.checks.biometry, "failed") },
            ]}
            onChange={(value) => {
              set("biometry", value);
            }}
          />
          <Choice
            label={ru.application.phoneOwner}
            value={state.phoneOwnerMatch ? "yes" : "no"}
            options={[
              { value: "yes", label: ru.common.yes },
              { value: "no", label: ru.common.no },
            ]}
            onChange={(value) => {
              set("phoneOwnerMatch", value === "yes");
            }}
          />
          <Choice<SelfBanChoice>
            label={ru.application.selfBan}
            value={state.selfBan}
            options={(["none", "active", "lifted"] as const).map((value) => ({
              value,
              label: label(t.selfBanChoice, value),
            }))}
            onChange={(value) => {
              set("selfBan", value);
            }}
          />
        </fieldset>

        <fieldset className={styles.section}>
          <legend className={styles.legend}>{t.sections.session}</legend>
          <p className={styles.hint}>{t.sessionHint}</p>
          <div className={styles.checks}>
            {SESSION_EVENTS.map((eventType) => (
              <label key={eventType} className={styles.check}>
                <input
                  type="checkbox"
                  checked={state.sessionEvents.includes(eventType)}
                  onChange={(event) => {
                    set(
                      "sessionEvents",
                      event.target.checked
                        ? [...state.sessionEvents, eventType]
                        : state.sessionEvents.filter((item) => item !== eventType),
                    );
                  }}
                />
                <span>{label(t.sessionEvents, eventType)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className={styles.footer}>
          {Object.keys(errors).length > 0 ? <InlineError message={t.formHasErrors} /> : null}
          {submit.isError ? <InlineError message={errorMessage(submit.error)} /> : null}
          {unmapped.map((message) => (
            <InlineError key={message} message={message} />
          ))}
          <Button type="submit" variant="primary" wide pending={submit.isPending}>
            {t.submit}
          </Button>
        </div>
      </form>
    </Card>
  );
}
