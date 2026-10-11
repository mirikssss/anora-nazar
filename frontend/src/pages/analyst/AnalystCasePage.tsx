// «/analyst/cases/:caseId» — дело онлайн-канала: причины, звонок по скрипту, исход.
import { useParams } from "react-router";

import { ru } from "@/shared/i18n/ru";
import { PageHeader } from "@/shared/ui/PageHeader";
import { AnalystWorkspace } from "@/widgets/analyst-workspace";

export function AnalystCasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  return (
    <>
      <PageHeader title={ru.analyst.title} subtitle={ru.analyst.subtitle} />
      <AnalystWorkspace caseId={caseId ?? null} />
    </>
  );
}
