// Маршруты страниц и доступ по правам ролей (таблица «Роли и страницы»).
import type { ReactNode } from "react";
import { createBrowserRouter } from "react-router";

import { AuditPage } from "@/pages/risk/AuditPage";
import { ConveyorPage } from "@/pages/bank/ConveyorPage";
import { CoreBankingPage } from "@/pages/bank/CoreBankingPage";
import { DecisionPage } from "@/pages/decisions/DecisionPage";
import { EntryPage } from "@/pages/entry/EntryPage";
import { NotFoundPage } from "@/pages/not-found/NotFoundPage";
import { PendingPage } from "@/pages/pending/PendingPage";
import { PERMISSIONS } from "@/shared/config/permissions";

import { Layout } from "./Layout";
import { RequirePermission } from "./RequirePermission";

const guarded = (permission: string, element: ReactNode) => (
  <RequirePermission permission={permission}>{element}</RequirePermission>
);

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <EntryPage /> },
      { path: "/bank/conveyor", element: guarded(PERMISSIONS.submitApplications, <ConveyorPage />) },
      { path: "/bank/core-banking", element: guarded(PERMISSIONS.executeCoreBanking, <CoreBankingPage />) },
      { path: "/decisions/:decisionId", element: guarded(PERMISSIONS.viewDecisions, <DecisionPage />) },
      { path: "/risk/audit", element: guarded(PERMISSIONS.viewAudit, <AuditPage />) },
      // Экраны Ф2–Ф3: появятся вместе с API на бэке (frontend/ITERATIONS.md).
      { path: "/borrower", element: guarded(PERMISSIONS.submitOnline, <PendingPage />) },
      { path: "/analyst/*", element: guarded(PERMISSIONS.viewOnlineCases, <PendingPage />) },
      { path: "/control/*", element: guarded(PERMISSIONS.viewGroupCases, <PendingPage />) },
      { path: "/risk", element: guarded(PERMISSIONS.viewQuality, <PendingPage />) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
