// Экран заявки в приложении заёмщика. Какой экран — решает бэк (поле screen), тексты — каталог узла для
// клиента. Зелёный — только шаги банка; жёлтый — вопросы; красный — прерывание с одной кнопкой «Понятно»,
// без «продолжить»: снять паузу из приложения нельзя (Блок 5).
import { useBorrowerApplication, AppScreen, type BorrowerApplication } from "@/entities/borrower";
import { useClientTexts, type ClientScreen, type ClientTexts } from "@/entities/texts";
import { CancelApplication } from "@/features/borrower-cancel";
import { IntentCheck } from "@/features/intent-check";
import { errorMessage } from "@/shared/api";
import { ru } from "@/shared/i18n/ru";
import { formatSum } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { Skeleton } from "@/shared/ui/Skeleton";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList } from "@/shared/ui/SummaryList";

import styles from "./BorrowerScreen.module.css";

const t = ru.borrower;

/** Экраны, где заёмщику называют общую причину проверки — без названия признака. */
const SCREENS_WITH_REASONS: readonly string[] = ["intent_check", "pause", "under_review", "stopped"];
/** Кнопки, которые просто закрывают экран и возвращают к списку заявок. */
const CLOSING_BUTTONS: readonly string[] = ["ok", "continue"];
const CANCEL_BUTTON = "cancel_application";

/** GOV.UK Warning text: знак «!» и жирное последствие. */
function Warning({ text }: { text: string }) {
  return (
    <p className={styles.warning}>
      <span className={styles.sign} aria-hidden>
        !
      </span>
      <strong>
        <span className="visually-hidden">{t.warningSign}: </span>
        {text}
      </strong>
    </p>
  );
}

function reasonTexts(application: BorrowerApplication, reasons: ClientTexts["reasons"]): string[] {
  if (!SCREENS_WITH_REASONS.includes(application.screen)) return [];
  return [...new Set(application.reason_codes.flatMap((code) => reasons[code] ?? []))];
}

interface ScreenBodyProps {
  application: BorrowerApplication;
  screen: ClientScreen;
  texts: ClientTexts;
  onClose: () => void;
}

function ScreenActions({ application, screen, onClose }: Omit<ScreenBodyProps, "texts">) {
  const codes = Object.keys(screen.buttons);
  return codes.map((code, index) => {
    const label = screen.buttons[code] ?? code;
    if (CLOSING_BUTTONS.includes(code)) {
      return (
        <Button key={code} variant={index === 0 ? "primary" : "secondary"} wide onClick={onClose}>
          {label}
        </Button>
      );
    }
    if (code === CANCEL_BUTTON && application.can_cancel) {
      return <CancelApplication key={code} applicationId={application.application_id} label={label} />;
    }
    return null;
  });
}

function ScreenBody({ application, screen, texts, onClose }: ScreenBodyProps) {
  const reasons = reasonTexts(application, texts.reasons);
  const details = (
    <>
      {reasons.map((text) => (
        <p key={text} className={styles.reason}>
          {text}
        </p>
      ))}
      {screen.warning !== null ? <Warning text={screen.warning} /> : null}
    </>
  );

  if (application.screen === "pause") {
    return (
      <div className={styles.interruption} role="alert">
        <AppScreen
          title={screen.title}
          lead={screen.body}
          actions={<ScreenActions application={application} screen={screen} onClose={onClose} />}
        >
          {details}
        </AppScreen>
      </div>
    );
  }

  if (application.screen === "intent_check") {
    return (
      <AppScreen title={screen.title} lead={screen.body}>
        {reasons.length > 0 || screen.warning !== null ? details : null}
        <IntentCheck
          application={application}
          screen={screen}
          questionTexts={texts.verification_questions}
          onPostpone={onClose}
        />
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title={screen.title}
      lead={screen.body}
      actions={<ScreenActions application={application} screen={screen} onClose={onClose} />}
    >
      {application.screen === "approved" ? (
        <SummaryList
          rows={[
            {
              key: "amount",
              label: t.loanAmount,
              value: <span className="num">{formatSum(application.loan.amount)}</span>,
            },
            {
              key: "term",
              label: t.loanTerm,
              value: `${String(application.loan.term_months)} ${ru.common.months}`,
            },
          ]}
        />
      ) : null}
      {details}
    </AppScreen>
  );
}

export function BorrowerScreen({ applicationId, onClose }: { applicationId: string; onClose: () => void }) {
  const application = useBorrowerApplication(applicationId);
  const texts = useClientTexts();
  if (application.isPending || texts.isPending) return <Skeleton rows={6} label={t.screenLoading} />;
  if (application.isError || texts.isError) {
    return (
      <StateMessage
        tone="error"
        title={ru.errors.loadFailed}
        description={errorMessage(application.error ?? texts.error)}
        action={
          <Button
            onClick={() => {
              void application.refetch();
              void texts.refetch();
            }}
          >
            {ru.common.retry}
          </Button>
        }
      />
    );
  }
  const screen = texts.data.client_screens[application.data.screen];
  if (screen === undefined) {
    return <StateMessage tone="error" title={ru.errors.loadFailed} description={application.data.screen} />;
  }
  // key: новый экран — новое состояние (выбранные ответы не переносятся между экранами).
  return (
    <ScreenBody
      key={application.data.screen}
      application={application.data}
      screen={screen}
      texts={texts.data}
      onClose={onClose}
    />
  );
}
