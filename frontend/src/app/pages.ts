// Страницы ролей грузятся по маршруту: проверяющий с телефона не качает граф, графики и экраны чужих ролей.
import { lazy } from "react";

export const AnalystQueuePage = lazy(() =>
  import("@/pages/analyst/AnalystQueuePage").then((m) => ({ default: m.AnalystQueuePage })),
);
export const AnalystCasePage = lazy(() =>
  import("@/pages/analyst/AnalystCasePage").then((m) => ({ default: m.AnalystCasePage })),
);
export const ConveyorPage = lazy(() =>
  import("@/pages/bank/ConveyorPage").then((m) => ({ default: m.ConveyorPage })),
);
export const CoreBankingPage = lazy(() =>
  import("@/pages/bank/CoreBankingPage").then((m) => ({ default: m.CoreBankingPage })),
);
export const BorrowerAppPage = lazy(() =>
  import("@/pages/borrower/BorrowerAppPage").then((m) => ({ default: m.BorrowerAppPage })),
);
export const ControlCasesPage = lazy(() =>
  import("@/pages/control/ControlCasesPage").then((m) => ({ default: m.ControlCasesPage })),
);
export const ControlCasePage = lazy(() =>
  import("@/pages/control/ControlCasePage").then((m) => ({ default: m.ControlCasePage })),
);
export const DecisionPage = lazy(() =>
  import("@/pages/decisions/DecisionPage").then((m) => ({ default: m.DecisionPage })),
);
export const RiskOverviewPage = lazy(() =>
  import("@/pages/risk/RiskOverviewPage").then((m) => ({ default: m.RiskOverviewPage })),
);
export const PolicyPage = lazy(() =>
  import("@/pages/risk/PolicyPage").then((m) => ({ default: m.PolicyPage })),
);
export const ModelQualityPage = lazy(() =>
  import("@/pages/risk/ModelQualityPage").then((m) => ({ default: m.ModelQualityPage })),
);
export const AuditPage = lazy(() => import("@/pages/risk/AuditPage").then((m) => ({ default: m.AuditPage })));
