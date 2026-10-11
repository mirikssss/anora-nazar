// Маршруты страниц и доступ по правам ролей (таблица «Роли и страницы»).
import type { ReactNode } from "react";
import { createBrowserRouter } from "react-router";

import { EntryPage } from "@/pages/entry/EntryPage";
import { NotFoundPage } from "@/pages/not-found/NotFoundPage";
import { PERMISSIONS } from "@/shared/config/permissions";

import { Layout } from "./Layout";
import {
  AnalystCasePage,
  AnalystQueuePage,
  AuditPage,
  BorrowerAppPage,
  ControlCasePage,
  ControlCasesPage,
  ConveyorPage,
  CoreBankingPage,
  DecisionPage,
  ModelQualityPage,
  PolicyPage,
  RiskOverviewPage,
} from "./pages";
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
      { path: "/risk/models", element: guarded(PERMISSIONS.viewQuality, <ModelQualityPage />) },
      { path: "/risk/audit", element: guarded(PERMISSIONS.viewAudit, <AuditPage />) },
      { path: "/borrower", element: guarded(PERMISSIONS.submitOnline, <BorrowerAppPage />) },
      { path: "/analyst", element: guarded(PERMISSIONS.viewOnlineCases, <AnalystQueuePage />) },
      { path: "/analyst/cases/:caseId", element: guarded(PERMISSIONS.viewOnlineCases, <AnalystCasePage />) },
      { path: "/control", element: guarded(PERMISSIONS.viewGroupCases, <ControlCasesPage />) },
      { path: "/control/cases/:caseId", element: guarded(PERMISSIONS.viewGroupCases, <ControlCasePage />) },
      { path: "/risk", element: guarded(PERMISSIONS.viewQuality, <RiskOverviewPage />) },
      { path: "/risk/policy", element: guarded(PERMISSIONS.proposePolicy, <PolicyPage />) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
