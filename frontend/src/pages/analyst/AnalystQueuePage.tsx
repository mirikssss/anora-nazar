// «/analyst» — очередь антифрод-центра; дело ещё не выбрано.
import { ru } from "@/shared/i18n/ru";
import { PageHeader } from "@/shared/ui/PageHeader";
import { AnalystWorkspace } from "@/widgets/analyst-workspace";

export function AnalystQueuePage() {
  return (
    <>
      <PageHeader title={ru.analyst.title} subtitle={ru.analyst.subtitle} />
      <AnalystWorkspace caseId={null} />
    </>
  );
}
