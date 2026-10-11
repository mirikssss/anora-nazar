// Страница не найдена.
import { Link } from "react-router";

import { ru } from "@/shared/i18n/ru";
import { StateMessage } from "@/shared/ui/StateMessage";

export function NotFoundPage() {
  return (
    <StateMessage
      title={ru.notFound.title}
      description={ru.notFound.body}
      action={<Link to="/">{ru.notFound.home}</Link>}
    />
  );
}
