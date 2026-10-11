// Страница открывается только роли с нужным правом; иначе — объяснение и вход нужной ролью.
import type { ReactNode } from "react";

import { hasPermission, useSession } from "@/entities/session";
import { AccessPrompt } from "@/pages/entry/AccessPrompt";

export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const session = useSession();
  return hasPermission(session, permission) ? children : <AccessPrompt permission={permission} />;
}
