// Общий каркас всех страниц: шапка с разделами роли и содержимое маршрута.
import { Suspense } from "react";
import { Outlet } from "react-router";

import { useSession } from "@/entities/session";
import { ru } from "@/shared/i18n/ru";
import { Skeleton } from "@/shared/ui/Skeleton";
import { AppShell } from "@/widgets/app-shell/AppShell";

import { navigationFor } from "./navigation";

export function Layout() {
  const session = useSession();
  return (
    <AppShell nav={navigationFor(session)}>
      <Suspense fallback={<Skeleton rows={6} label={ru.common.loading} />}>
        <Outlet />
      </Suspense>
    </AppShell>
  );
}
