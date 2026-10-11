// Проверка намерения (жёлтый): вопросы с ответами кнопками, «Продолжить», «Отложить» и «Меня просят
// взять кредит» — эта кнопка видна сразу и отправляет сигнал молча, без вопроса «вы уверены?» (Блок 5).
import { useState } from "react";

import {
  answerIntent,
  reportPressure,
  useBorrowerAction,
  type BorrowerApplication,
  type IntentAnswer,
} from "@/entities/borrower";
import type { ClientScreen, ClientTexts } from "@/entities/texts";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

import styles from "./IntentCheck.module.css";

interface IntentCheckProps {
  application: BorrowerApplication;
  screen: ClientScreen;
  questionTexts: ClientTexts["verification_questions"];
  onPostpone: () => void;
}

export function IntentCheck({ application, screen, questionTexts, onPostpone }: IntentCheckProps) {
  const [chosen, setChosen] = useState<Readonly<Record<string, string>>>({});
  const answer = useBorrowerAction((answers: IntentAnswer[]) =>
    answerIntent(application.application_id, answers),
  );
  const pressure = useBorrowerAction(() => reportPressure(application.application_id));
  const questions = application.questions?.questions ?? [];
  const complete = questions.length > 0 && questions.every((question) => chosen[question.code] !== undefined);
  const { buttons } = screen;
  const error = answer.error ?? pressure.error;

  return (
    <div className={styles.check}>
      {application.questions_unavailable ? <p>{ru.borrower.questionsUnavailable}</p> : null}
      {questions.map((question) => {
        const text = questionTexts[question.code];
        return (
          <fieldset key={question.code} className={styles.question}>
            <legend className={styles.text}>{text?.text ?? question.code}</legend>
            <div className={styles.answers}>
              {question.answers.map((option) => (
                <label key={option.code} className={styles.answer}>
                  <input
                    type="radio"
                    name={question.code}
                    value={option.code}
                    checked={chosen[question.code] === option.code}
                    className="visually-hidden"
                    onChange={() => {
                      setChosen((current) => ({ ...current, [question.code]: option.code }));
                    }}
                  />
                  <span>{text?.answers[option.code] ?? option.code}</span>
                </label>
              ))}
            </div>
          </fieldset>
        );
      })}
      {error !== null ? <InlineError message={errorMessage(error)} /> : null}
      <div className={styles.actions}>
        {buttons.continue !== undefined && questions.length > 0 ? (
          <Button
            variant="primary"
            wide
            disabled={!complete}
            pending={answer.isPending}
            title={complete ? undefined : ru.borrower.answerAll}
            onClick={() => {
              answer.mutate(
                questions.flatMap((question) => {
                  const code = chosen[question.code];
                  return code === undefined ? [] : [{ question: question.code, answer: code }];
                }),
              );
            }}
          >
            {buttons.continue}
          </Button>
        ) : null}
        {buttons.postpone !== undefined ? (
          <Button wide onClick={onPostpone}>
            {buttons.postpone}
          </Button>
        ) : null}
        {buttons.someone_asks !== undefined ? (
          <Button
            variant="alarm"
            wide
            pending={pressure.isPending}
            onClick={() => {
              pressure.mutate();
            }}
          >
            {buttons.someone_asks}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
