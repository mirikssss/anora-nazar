// Разделы шапки по правам текущей роли — пути из таблицы «Роли и страницы» (CLAUDE.md).
import { hasPermission, type VisitorSession } from "@/entities/session";
import { PERMISSIONS } from "@/shared/config/permissions";
import type { NavItem } from "@/widgets/app-shell/AppShell";
import { ru } from "@/shared/i18n/ru";

const SECTIONS: readonly (NavItem & { permission: string })[] = [
  { to: "/borrower", label: ru.nav.borrower, permission: PERMISSIONS.submitOnline },
  { to: "/bank/conveyor", label: ru.nav.conveyor, permission: PERMISSIONS.submitApplications },
  { to: "/bank/core-banking", label: ru.nav.coreBanking, permission: PERMISSIONS.executeCoreBanking },
  { to: "/analyst", label: ru.nav.analystQueue, permission: PERMISSIONS.viewOnlineCases },
  { to: "/control", label: ru.nav.controlCases, permission: PERMISSIONS.viewGroupCases },
  { to: "/risk", label: ru.nav.riskOverview, permission: PERMISSIONS.viewQuality, end: true },
  { to: "/risk/policy", label: ru.nav.policy, permission: PERMISSIONS.proposePolicy },
  { to: "/risk/models", label: ru.nav.models, permission: PERMISSIONS.viewQuality },
  { to: "/risk/network", label: ru.nav.network, permission: PERMISSIONS.viewQuality },
  { to: "/risk/audit", label: ru.nav.audit, permission: PERMISSIONS.viewAudit },
];

export function navigationFor(session: VisitorSession): NavItem[] {
  return SECTIONS.filter((section) => hasPermission(session, section.permission)).map(({ to, label, end }) =>
    end === undefined ? { to, label } : { to, label, end },
  );
}
