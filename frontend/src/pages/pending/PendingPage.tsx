// Временная страница раздела, у которого ещё нет API на бэке (Ф2–Ф3, frontend/ITERATIONS.md).
import { ru } from "@/shared/i18n/ru";
import { StateMessage } from "@/shared/ui/StateMessage";

export function PendingPage() {
  return <StateMessage title={ru.pending.title} description={ru.pending.body} />;
}
