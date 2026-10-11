// Акт приёмки по программной заявке (Т5): кто подписал, когда и на какую сумму счёта. По акту АБС затем
// запрашивает у узла разрешение на оплату поставщику.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { snapshotView, useApplications } from "@/entities/application";
import {
  createAct,
  programKeys,
  SIGNER_ROLES,
  useActs,
  useHelpers,
  type AcceptanceAct,
  type SignerRole,
} from "@/entities/program";
import { ApiError, errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatDate, formatSum, parseInteger } from "@/shared/lib/format";
import { str } from "@/shared/lib/json";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { Choice } from "@/shared/ui/Choice";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";

import styles from "./AcceptanceActPanel.module.css";
import { isOtherSigner, signerExample, todayExample } from "./example";

const t = ru.borrower.acts;
const PROGRAM = "program";
const CANCELLED = "cancelled";
const HELPER: SignerRole = "helper";

function ActList({ applicationId, onPay }: { applicationId: string; onPay: (act: AcceptanceAct) => void }) {
  const acts = useActs(applicationId);
  if (acts.isPending) return <Skeleton rows={2} label={ru.common.loading} />;
  if (acts.isError) return <InlineError message={errorMessage(acts.error)} />;
  if (acts.data.length === 0) return <p className={styles.hint}>{t.empty}</p>;
  return (
    <ul className={styles.list}>
      {acts.data.map((act) => (
        <li key={act.act_id} className={styles.act}>
          <div className={styles.actText}>
            <span className={styles.actHead}>
              <code>{act.act_id}</code>
              <span className="num">{formatSum(act.invoice_amount)}</span>
            </span>
            <span className={styles.hint}>
              {label(t.signerRoles, act.signer_role)} · {act.signer_id} · {formatDate(act.signed_on)}
            </span>
          </div>
          <Button
            size="sm"
            onClick={() => {
              onPay(act);
            }}
          >
            {t.pay}
          </Button>
        </li>
      ))}
    </ul>
  );
}

interface AcceptanceActPanelProps {
  initialApplicationId: string | null;
  onPay: (act: AcceptanceAct) => void;
}

export function AcceptanceActPanel({ initialApplicationId, onPay }: AcceptanceActPanelProps) {
  const queryClient = useQueryClient();
  const applications = useApplications();
  const [applicationId, setApplicationId] = useState(initialApplicationId ?? "");
  const [role, setRole] = useState<SignerRole>(HELPER);
  const [signerId, setSignerId] = useState("");
  const [signedOn, setSignedOn] = useState("");
  const [invoice, setInvoice] = useState("");
  const [signerSuggestion, setSignerSuggestion] = useState<Partial<Record<SignerRole, string>>>({});

  const programs = (applications.data ?? []).filter(
    (app) => app.channel === PROGRAM && app.status !== CANCELLED,
  );
  const chosen = programs.find((app) => app.id === applicationId);
  const view = chosen ? snapshotView(chosen) : null;
  const district = str(view?.program?.district);
  const helpers = useHelpers(district);
  const create = useMutation({
    mutationFn: createAct,
    onSuccess: () => {
      setSignerId("");
      setInvoice("");
      setSignerSuggestion({});
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: programKeys.acts(applicationId) }),
  });

  const amount = parseInteger(invoice);
  const fields = create.error instanceof ApiError ? create.error.fields : {};
  const invoiceExample = view?.amount != null ? String(view.amount) : "";
  const otherExample = isOtherSigner(role) ? (signerSuggestion[role] ?? signerExample(role)) : "";
  const today = todayExample();

  const chooseRole = (next: SignerRole) => {
    setRole(next);
    setSignerId("");
    if (isOtherSigner(next) && signerSuggestion[next] === undefined) {
      setSignerSuggestion((current) => ({ ...current, [next]: signerExample(next) }));
    }
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (applicationId === "" || signerId.trim() === "" || signedOn === "" || amount === null) return;
    create.mutate({
      application_id: applicationId,
      signer_id: signerId.trim(),
      signer_role: role,
      signed_on: signedOn,
      invoice_amount: amount,
    });
  };

  return (
    <Card title={t.title} subtitle={t.subtitle}>
      <div className={styles.body}>
        <form className={styles.form} noValidate onSubmit={onSubmit}>
          <SelectField
            label={t.application}
            value={applicationId}
            placeholder={t.applicationPlaceholder}
            options={programs.map((app) => ({ value: app.id, label: app.id }))}
            hint={applications.isSuccess && programs.length === 0 ? t.noApplications : undefined}
            onChange={(event) => {
              setApplicationId(event.target.value);
              setSignerId("");
            }}
          />
          <Choice
            label={t.signerRole}
            value={role}
            options={SIGNER_ROLES.map((value) => ({ value, label: label(t.signerRoles, value) }))}
            onChange={chooseRole}
          />
          {role === HELPER ? (
            <SelectField
              label={t.helper}
              value={signerId}
              placeholder={helpers.isPending ? t.helpersLoading : t.helperPlaceholder}
              options={(helpers.data ?? []).map((helper) => ({
                value: helper.id,
                label: `${helper.id} · ${helper.district}, ${helper.mahalla}`,
              }))}
              error={fields.signer_id ?? (helpers.isError ? errorMessage(helpers.error) : undefined)}
              onChange={(event) => {
                setSignerId(event.target.value);
              }}
            />
          ) : (
            <TextField
              label={t.signerId}
              value={signerId}
              error={fields.signer_id}
              suggestion={{
                value: otherExample,
                onAccept: () => {
                  setSignerId(otherExample);
                },
              }}
              onChange={(event) => {
                setSignerId(event.target.value);
              }}
            />
          )}
          <div className={styles.grid}>
            <TextField
              label={t.signedOn}
              value={signedOn}
              error={fields.signed_on}
              suggestion={{
                value: today,
                onAccept: () => {
                  setSignedOn(today);
                },
              }}
              onChange={(event) => {
                setSignedOn(event.target.value);
              }}
            />
            <TextField
              label={t.invoiceAmount}
              value={invoice}
              inputMode="numeric"
              hint={amount !== null ? formatSum(amount) : undefined}
              error={
                fields.invoice_amount ??
                (invoice.trim() !== "" && amount === null ? ru.conveyor.notNumber : undefined)
              }
              suggestion={
                invoiceExample === ""
                  ? undefined
                  : {
                      value: invoiceExample,
                      onAccept: () => {
                        setInvoice(invoiceExample);
                      },
                    }
              }
              onChange={(event) => {
                setInvoice(event.target.value);
              }}
            />
          </div>
          {create.isError ? <InlineError message={errorMessage(create.error)} /> : null}
          <Button
            type="submit"
            variant="primary"
            wide
            pending={create.isPending}
            disabled={applicationId === "" || signerId.trim() === "" || signedOn === "" || amount === null}
          >
            {t.submit}
          </Button>
        </form>
        {applicationId !== "" ? (
          <section className={styles.section}>
            <h3 className={styles.heading}>{t.listTitle}</h3>
            <ActList applicationId={applicationId} onPay={onPay} />
          </section>
        ) : null}
      </div>
    </Card>
  );
}
