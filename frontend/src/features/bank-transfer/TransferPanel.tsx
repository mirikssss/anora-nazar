// Перевод с карты после зачисления (Т3): банк спрашивает узел, узел рекомендует, решает ТАФ банка.
// Удержанный перевод банк отправляет или отменяет после подтверждения клиента по независимому каналу.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { snapshotView, useApplications } from "@/entities/application";
import { LevelBadge } from "@/entities/decision";
import { titleOf, useStaffTexts } from "@/entities/texts";
import {
  createTransfer,
  decideTransfer,
  HELD_STATUS,
  nodeErrorMessage,
  ownRuleHold,
  recommendation,
  transferKeys,
  useTransfers,
  type Transfer,
  type TransferAction,
} from "@/entities/transfer";
import { ApiError, errorMessage } from "@/shared/api";
import { label, ru } from "@/shared/i18n/ru";
import { formatShare, formatSum, formatTime, parseInteger } from "@/shared/lib/format";
import { Badge, type BadgeTone } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { SelectField, TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";

import { exampleAmount, makeExample } from "./example";
import styles from "./TransferPanel.module.css";

const t = ru.borrower.transfers;
const ONLINE = "online";
const CANCELLED = "cancelled";
const STATUS_TONES: Readonly<Record<string, BadgeTone>> = { executed: "green", held: "orange" };

function useInvalidateTransfers(applicationId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: transferKeys.byApplication(applicationId) });
}

function TransferDecision({ transfer }: { transfer: Transfer }) {
  const invalidate = useInvalidateTransfers(transfer.application_id);
  const decide = useMutation({
    mutationFn: (action: TransferAction) => decideTransfer(transfer.transfer_id, action),
    onSettled: invalidate,
  });
  return (
    <div className={styles.decision}>
      <p className={styles.hint}>{t.decisionHint}</p>
      <div className={styles.buttons}>
        <Button
          size="sm"
          variant="primary"
          disabled={decide.isPending}
          onClick={() => {
            decide.mutate("release");
          }}
        >
          {t.release}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={decide.isPending}
          onClick={() => {
            decide.mutate("cancel");
          }}
        >
          {t.cancel}
        </Button>
      </div>
      {decide.isError ? <InlineError message={errorMessage(decide.error)} /> : null}
    </div>
  );
}

function TransferItem({ transfer }: { transfer: Transfer }) {
  const texts = useStaffTexts().data;
  const advice = recommendation(transfer);
  const hold = ownRuleHold(transfer);
  const nodeError = nodeErrorMessage(transfer);
  const action = advice?.recommendedAction ?? null;
  const actionText = action !== null ? texts?.transfer_actions[action] : undefined;
  const rows: SummaryRow[] = [
    { key: "card", label: t.card, value: <code>{transfer.recipient_card}</code> },
    { key: "new", label: t.newRecipient, value: transfer.recipient_is_new ? ru.common.yes : ru.common.no },
    {
      key: "share",
      label: t.creditShare,
      value: <span className="num">{formatShare(transfer.credit_share)}</span>,
    },
    { key: "by", label: ru.decision.action, value: label(t.decidedBy, transfer.decided_by) },
  ];
  if (hold !== null) {
    rows.push({ key: "rule", label: t.ownRule, value: hold ? t.ownRuleHold : t.ownRuleAllow });
  }
  if (transfer.resolution !== null) {
    rows.push({
      key: "resolution",
      label: ru.decision.outcome,
      value: label(t.resolutions, transfer.resolution),
    });
  }
  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        <span className={`${styles.amount} num`}>{formatSum(transfer.amount)}</span>
        <Badge tone={STATUS_TONES[transfer.status] ?? "neutral"}>{label(t.statuses, transfer.status)}</Badge>
        <span className={styles.time}>{formatTime(transfer.created_at)}</span>
      </div>
      {advice !== null ? (
        <section className={styles.advice}>
          <div className={styles.adviceHead}>
            <span className={styles.adviceLabel}>{t.recommendation}</span>
            <LevelBadge level={advice.level} />
          </div>
          {action !== null ? (
            <p>
              <strong>{actionText?.title ?? action}</strong>
              {actionText?.description ? ` — ${actionText.description}` : null}
            </p>
          ) : null}
          {advice.reasons.length > 0 ? (
            <ul className={styles.reasons}>
              {advice.reasons.map((reason) => (
                <li key={reason.code}>
                  {titleOf(texts?.reasons, reason.code)}
                  {reason.norm ? <span className={styles.norm}> · {reason.norm}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
          {actionText !== undefined ? (
            <p className={styles.hint}>
              {t.clientSees}: «{actionText.client_message}»
            </p>
          ) : null}
        </section>
      ) : (
        <p className={styles.hint}>
          {nodeError !== null ? `${t.noRecommendation}: ${nodeError}` : t.noRecommendation}
        </p>
      )}
      <SummaryList rows={rows} />
      {transfer.status === HELD_STATUS && transfer.resolution === null ? (
        <TransferDecision transfer={transfer} />
      ) : null}
    </li>
  );
}

function TransferList({ applicationId }: { applicationId: string }) {
  const transfers = useTransfers(applicationId);
  if (transfers.isPending) return <Skeleton rows={2} label={t.loading} />;
  if (transfers.isError) return <InlineError message={errorMessage(transfers.error)} />;
  if (transfers.data.length === 0) return <p className={styles.hint}>{t.empty}</p>;
  return (
    <ul className={styles.list}>
      {transfers.data.map((transfer) => (
        <TransferItem key={transfer.transfer_id} transfer={transfer} />
      ))}
    </ul>
  );
}

export function TransferPanel({ initialApplicationId }: { initialApplicationId: string | null }) {
  const applications = useApplications();
  const [applicationId, setApplicationId] = useState(initialApplicationId ?? "");
  const [recipientCard, setRecipientCard] = useState("");
  const [amount, setAmount] = useState("");
  const [example, setExample] = useState(makeExample);
  const invalidate = useInvalidateTransfers(applicationId);
  const send = useMutation({
    mutationFn: createTransfer,
    onSuccess: () => {
      setRecipientCard("");
      setAmount("");
      setExample(makeExample());
    },
    onSettled: invalidate,
  });
  const online = (applications.data ?? []).filter(
    (app) => app.channel === ONLINE && app.status !== CANCELLED,
  );
  const chosen = online.find((app) => app.id === applicationId);
  const suggestedAmount = exampleAmount(example, chosen ? snapshotView(chosen).amount : null);
  const parsedAmount = parseInteger(amount);
  const fields = send.error instanceof ApiError ? send.error.fields : {};

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (applicationId === "" || parsedAmount === null) return;
    send.mutate({
      application_id: applicationId,
      recipient_card: recipientCard.trim(),
      amount: parsedAmount,
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
            options={online.map((app) => ({ value: app.id, label: app.id }))}
            hint={applications.isSuccess && online.length === 0 ? t.noApplications : undefined}
            onChange={(event) => {
              setApplicationId(event.target.value);
            }}
          />
          <TextField
            label={t.card}
            value={recipientCard}
            inputMode="numeric"
            error={fields.recipient_card}
            suggestion={{
              value: example.card,
              onAccept: () => {
                setRecipientCard(example.card);
              },
            }}
            onChange={(event) => {
              setRecipientCard(event.target.value);
            }}
          />
          <TextField
            label={t.amount}
            value={amount}
            inputMode="numeric"
            hint={parsedAmount !== null ? formatSum(parsedAmount) : undefined}
            error={
              fields.amount ??
              (amount.trim() !== "" && parsedAmount === null ? ru.conveyor.notNumber : undefined)
            }
            suggestion={
              suggestedAmount === ""
                ? undefined
                : {
                    value: suggestedAmount,
                    onAccept: () => {
                      setAmount(suggestedAmount);
                    },
                  }
            }
            onChange={(event) => {
              setAmount(event.target.value);
            }}
          />
          {send.isError ? <InlineError message={errorMessage(send.error)} /> : null}
          <Button
            type="submit"
            variant="primary"
            wide
            pending={send.isPending}
            disabled={applicationId === "" || recipientCard.trim() === "" || parsedAmount === null}
          >
            {t.submit}
          </Button>
        </form>
        {applicationId !== "" ? (
          <section className={styles.section}>
            <h3 className={styles.heading}>{t.listTitle}</h3>
            <TransferList applicationId={applicationId} />
          </section>
        ) : null}
      </div>
    </Card>
  );
}
