// Общий каркас всех страниц: шапка с разделами роли и содержимое маршрута.
import { Outlet } from "react-router";

import { useSession } from "@/entities/session";
import { AppShell } from "@/widgets/app-shell/AppShell";

import { navigationFor } from "./navigation";

export function Layout() {
  const session = useSession();
  return (
    <AppShell nav={navigationFor(session)}>
      <Outlet />
    </AppShell>
  );
}
