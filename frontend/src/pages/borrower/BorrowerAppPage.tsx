// «/borrower» — приложение заёмщика: выбор клиента, заявка, экран по заявке (проверка намерения, пауза).
// На широком экране — в рамке телефона, рядом пульт симулятора с заявками сценариев.
import { useSearchParams } from "react-router";

import { usePersonas } from "@/entities/borrower";
import { ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Skeleton } from "@/shared/ui/Skeleton";
import { BorrowerHome } from "@/widgets/borrower-home";
import { PersonaPicker } from "@/widgets/borrower-personas";
import { ScenarioApplications } from "@/widgets/borrower-scenarios";
import { BorrowerScreen } from "@/widgets/borrower-screen";
import { PhoneFrame } from "@/widgets/phone-frame/PhoneFrame";

import styles from "./BorrowerAppPage.module.css";

const PERSONA = "persona";
const APPLICATION = "application";

function useAppLocation() {
  const [params, setParams] = useSearchParams();
  const update = (key: string, value: string | null) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === null) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );
  };
  return {
    personaCode: params.get(PERSONA),
    applicationId: params.get(APPLICATION),
    openApplication: (applicationId: string | null) => {
      update(APPLICATION, applicationId);
    },
    choosePersona: (personaCode: string | null) => {
      update(PERSONA, personaCode);
    },
  };
}

function BorrowerApp() {
  const { personaCode, applicationId, openApplication, choosePersona } = useAppLocation();
  const personas = usePersonas();
  if (applicationId !== null) {
    return (
      <BorrowerScreen
        applicationId={applicationId}
        onClose={() => {
          openApplication(null);
        }}
      />
    );
  }
  if (personaCode === null) return <PersonaPicker onSelect={choosePersona} />;
  if (personas.isPending) return <Skeleton rows={5} label={ru.borrower.personasLoading} />;
  const persona = personas.data?.find((item) => item.code === personaCode);
  if (persona === undefined) return <PersonaPicker onSelect={choosePersona} />;
  return (
    <BorrowerHome
      persona={persona}
      onOpen={openApplication}
      onChangePersona={() => {
        choosePersona(null);
      }}
    />
  );
}

export function BorrowerAppPage() {
  const { applicationId, openApplication } = useAppLocation();
  return (
    <>
      <PageHeader
        title={ru.borrower.title}
        subtitle={ru.borrower.subtitle}
        tag={<Badge tone="outline">{ru.common.simulator}</Badge>}
      />
      <div className={styles.layout}>
        <PhoneFrame label={ru.borrower.frameLabel}>
          <BorrowerApp />
        </PhoneFrame>
        <div className={styles.side}>
          <ScenarioApplications selectedId={applicationId} onOpen={openApplication} />
        </div>
      </div>
    </>
  );
}
