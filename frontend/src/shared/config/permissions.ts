// Коды прав из сидов ролей (backend/src/node/seeds, backend/src/bank_sim/seeds): по ним открываются страницы.
export const PERMISSIONS = {
  submitApplications: "applications.submit",
  executeCoreBanking: "core_banking.execute",
  viewDecisions: "decisions.view",
  viewOnlineCases: "cases.online.view",
  viewGroupCases: "cases.group.view",
  viewQuality: "quality.view",
  viewAudit: "audit.view",
  verifyAudit: "audit.verify",
  submitOnline: "applications.online.submit",
} as const;
