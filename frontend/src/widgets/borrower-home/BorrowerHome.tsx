// Главный экран приложения клиента: одно действие — «Взять кредит», ниже — его заявки и их состояние.
import { useState } from "react";

import { AppScreen, useBorrowerApplications, type Persona } from "@/entities/borrower";
import { useClientTexts } from "@/entities/texts";
import { BorrowerApplyForm } from "@/features/borrower-apply";
import { errorMessage } from "@/shared/api";
import { IconForward } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { formatDate, formatSum } from "@/shared/lib/format";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";
import { Skeleton } from "@/shared/ui/Skeleton";

import styles from "./BorrowerHome.module.css";

const t = ru.borrower;

interface BorrowerHomeProps {
  persona: Persona;
  onOpen: (applicationId: string) => void;
  onChangePersona: () => void;
}

function Applications({ persona, onOpen }: Omit<BorrowerHomeProps, "onChangePersona">) {
  const applications = useBorrowerApplications(persona.code);
  const screens = useClientTexts().data?.client_screens;
  if (applications.isPending) return <Skeleton rows={3} label={t.applicationsLoading} />;
  if (applications.isError) return <InlineError message={errorMessage(applications.error)} />;
  if (applications.data.length === 0) return <p className={styles.empty}>{t.myApplicationsEmpty}</p>;
  return (
    <ul className={styles.list}>
      {applications.data.map((application) => (
        <li key={application.application_id}>
          <button
            type="button"
            className={styles.item}
            onClick={() => {
              onOpen(application.application_id);
            }}
          >
            <span className={styles.itemText}>
              <span className={`${styles.amount} num`}>{formatSum(application.loan.amount)}</span>
              <span className={styles.meta}>
                {screens?.[application.screen]?.title ?? application.screen} ·{" "}
                {formatDate(application.created_at)}
              </span>
            </span>
            <IconForward size={20} aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function BorrowerHome({ persona, onOpen, onChangePersona }: BorrowerHomeProps) {
  const [applying, setApplying] = useState(false);
  if (applying) {
    return (
      <AppScreen
        top={
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setApplying(false);
            }}
          >
            {ru.common.back}
          </Button>
        }
        title={t.applyTitle}
        lead={t.applyHint}
      >
        <BorrowerApplyForm
          personaCode={persona.code}
          onSubmitted={(application) => {
            setApplying(false);
            onOpen(application.application_id);
          }}
        />
      </AppScreen>
    );
  }
  return (
    <AppScreen
      top={
        <Button size="sm" variant="ghost" onClick={onChangePersona}>
          {t.changePersona}
        </Button>
      }
      title={`${t.greeting} ${persona.display_name}`}
    >
      <Button
        variant="primary"
        wide
        onClick={() => {
          setApplying(true);
        }}
      >
        {t.newApplication}
      </Button>
      <section className={styles.section}>
        <h3 className={styles.heading}>{t.myApplications}</h3>
        <Applications persona={persona} onOpen={onOpen} />
      </section>
    </AppScreen>
  );
}
