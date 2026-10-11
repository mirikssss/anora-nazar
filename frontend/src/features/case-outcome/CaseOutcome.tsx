// Звонок и исход дела (Alloy manual review): ответы кнопками, чек-лист, один из пяти исходов, заметка →
// одна запись в ленте и в журнале. Тексты вопросов, пунктов и исходов — из каталога node/texts.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { caseKeys, recordOutcome, type CaseDetail, type CaseOutcome as OutcomeBody } from "@/entities/case";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { DEMO, pick } from "@/shared/demo";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { Choice } from "@/shared/ui/Choice";
import { TextField } from "@/shared/ui/Field";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./CaseOutcome.module.css";

const t = ru.caseOutcome;

interface CaseOutcomeProps {
  detail: CaseDetail;
  canDecide: boolean;
}

export function CaseOutcome({ detail, canDecide }: CaseOutcomeProps) {
  const texts = useStaffTexts().data;
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [outcome, setOutcome] = useState<OutcomeBody["outcome"] | null>(null);
  const [note, setNote] = useState("");
  const [noteExample] = useState(() => pick(DEMO.notes));
  const save = useMutation({
    mutationFn: (body: OutcomeBody) => recordOutcome(detail.case_id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: caseKeys.detail(detail.case_id) }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: caseKeys.queues }),
  });
  const closed = detail.status === "closed";
  const disabled = closed || !canDecide;

  return (
    <div className={styles.outcome}>
      {detail.call_script.length > 0 ? (
        <section className={styles.section}>
          <div>
            <h3 className={styles.heading}>{t.callTitle}</h3>
            <p className={styles.hint}>{t.callSubtitle}</p>
          </div>
          {detail.call_script.map((question) => {
            const text = texts?.verification_questions[question.code];
            return (
              <Choice
                key={question.code}
                label={text?.text ?? question.code}
                value={answers[question.code] ?? null}
                options={question.answers.map((answer) => ({
                  value: answer,
                  label: text?.answers[answer] ?? answer,
                }))}
                onChange={(value) => {
                  setAnswers((current) => ({ ...current, [question.code]: value }));
                }}
              />
            );
          })}
        </section>
      ) : null}

      <section className={styles.section}>
        <h3 className={styles.heading}>{t.checklist}</h3>
        {detail.checklist_items.map((code) => {
          const item = texts?.checklist_items[code];
          return (
            <label key={code} className={styles.check}>
              <input
                type="checkbox"
                checked={checklist[code] === true}
                disabled={disabled}
                onChange={(event) => {
                  setChecklist((current) => ({ ...current, [code]: event.target.checked }));
                }}
              />
              <span>
                <span>{item?.title ?? code}</span>
                {item?.description ? <span className={styles.hint}>{item.description}</span> : null}
              </span>
            </label>
          );
        })}
      </section>

      <section className={styles.section}>
        <h3 className={styles.heading}>{t.outcome}</h3>
        <div className={styles.radios} role="radiogroup" aria-label={t.outcome}>
          {detail.allowed_outcomes.map((code) => {
            const item = texts?.case_outcomes[code];
            return (
              <label key={code} className={styles.radio}>
                <input
                  type="radio"
                  name={`outcome-${detail.case_id}`}
                  checked={outcome === code}
                  disabled={disabled}
                  onChange={() => {
                    setOutcome(code as OutcomeBody["outcome"]);
                  }}
                />
                <span>
                  <span>{titleOf(texts?.case_outcomes, code)}</span>
                  {item?.description ? <span className={styles.hint}>{item.description}</span> : null}
                </span>
              </label>
            );
          })}
        </div>
        <TextField
          label={t.note}
          value={note}
          disabled={disabled}
          suggestion={{
            value: noteExample,
            onAccept: () => {
              setNote(noteExample);
            },
          }}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
      </section>

      {save.isError ? <InlineError message={errorMessage(save.error)} /> : null}
      {closed ? (
        <p className={styles.hint}>
          {t.closed}
          {detail.outcome !== null ? `: ${titleOf(texts?.case_outcomes, detail.outcome)}` : ""}
        </p>
      ) : !canDecide ? (
        <p className={styles.hint}>{t.noPermission}</p>
      ) : (
        <Button
          variant="primary"
          wide
          pending={save.isPending}
          disabled={outcome === null}
          onClick={() => {
            if (outcome !== null) save.mutate({ outcome, checklist, answers, note });
          }}
        >
          {t.submit}
        </Button>
      )}
    </div>
  );
}
