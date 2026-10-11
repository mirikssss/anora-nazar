// Предложения порогов: что меняется и почему, кто предложил, статус; подтверждает другой сотрудник.
import {
  approveProposal,
  formatThreshold,
  policyKeys,
  thresholdTitle,
  type Proposal,
} from "@/entities/policy";
import { useStaffName } from "@/entities/risk";
import { hasPermission, useSession } from "@/entities/session";
import { SecondSignerApproval } from "@/features/risk-approval";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { Table, type Column } from "@/shared/ui/Table";

import styles from "./RiskPolicy.module.css";

const t = ru.risk.policy;

export function Proposals({ proposals }: { proposals: readonly Proposal[] }) {
  const session = useSession();
  const staffName = useStaffName();
  const columns: Column<Proposal>[] = [
    {
      key: "change",
      header: t.change,
      primary: true,
      render: (proposal) => (
        <span className={styles.stacked}>
          {Object.entries(proposal.changes).map(([path, value]) => (
            <span key={path}>
              {thresholdTitle(path)}: <span className="num">{formatThreshold(value)}</span>
            </span>
          ))}
          <span className={styles.muted}>{proposal.reason}</span>
        </span>
      ),
    },
    {
      key: "proposed",
      header: t.proposedBy,
      render: (proposal) => (
        <span className={styles.stacked}>
          <span>{staffName(proposal.proposed_by)}</span>
          <span className={styles.muted}>
            {formatDateTime(proposal.proposed_at)} · {t.base} {proposal.base_version}
          </span>
        </span>
      ),
    },
    {
      key: "status",
      header: t.status,
      render: (proposal) =>
        proposal.approved_by === null ? (
          <Badge tone="neutral" dot>
            {t.pending}
          </Badge>
        ) : (
          <span className={styles.stacked}>
            <Badge tone="green" dot>
              {t.approved}
            </Badge>
            <span className={styles.muted}>
              {t.approvedBy} {staffName(proposal.approved_by)}
              {proposal.approved_at !== null ? ` · ${formatDateTime(proposal.approved_at)}` : ""}
            </span>
            {proposal.resulting_version !== null ? (
              <span className={styles.muted}>
                {t.resulting} {proposal.resulting_version}
              </span>
            ) : null}
          </span>
        ),
    },
  ];
  if (hasPermission(session, PERMISSIONS.approvePolicy)) {
    columns.push({
      key: "approve",
      header: "",
      align: "end",
      render: (proposal) =>
        proposal.approved_by === null ? (
          <SecondSignerApproval
            requestedBy={proposal.proposed_by}
            approve={() => approveProposal(proposal.proposal_id)}
            invalidate={[policyKeys.overview]}
          />
        ) : null,
    });
  }
  return (
    <Card title={t.proposalsTitle} flush>
      {proposals.length === 0 ? (
        <StateMessage title={t.proposalsEmpty} />
      ) : (
        <Table
          caption={t.proposalsTitle}
          columns={columns}
          rows={proposals}
          rowKey={(proposal) => proposal.proposal_id}
        />
      )}
    </Card>
  );
}
