// Состояние сети в контуре: переключатель из действующей политики, ответ оператора, версия контракта.
// Включение и выключение — предложение порога со вторым подписантом прямо здесь.
import { networkKeys, type NetworkOverview } from "@/entities/network";
import { approveProposal, policyKeys, usePolicy } from "@/entities/policy";
import { useStaffName } from "@/entities/risk";
import { hasPermission, useSession } from "@/entities/session";
import { NetworkToggle } from "@/features/network-toggle";
import { SecondSignerApproval } from "@/features/risk-approval";
import { PERMISSIONS } from "@/shared/config/permissions";
import { ru } from "@/shared/i18n/ru";
import { formatDateTime, formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { SummaryList } from "@/shared/ui/SummaryList";

import styles from "./RiskNetwork.module.css";

const t = ru.risk.network;

function OperatorBadge({ overview }: { overview: NetworkOverview }) {
  if (!overview.configured) return <Badge tone="outline">{t.operatorNotConfigured}</Badge>;
  return overview.available ? (
    <Badge tone="green" dot>
      {t.operatorAvailable}
    </Badge>
  ) : (
    <Badge tone="red" dot>
      {t.operatorUnavailable}
    </Badge>
  );
}

function Toggle({ overview }: { overview: NetworkOverview }) {
  const session = useSession();
  const staffName = useStaffName();
  const policy = usePolicy();
  const pending = policy.data?.proposals.find(
    (proposal) => proposal.approved_by === null && overview.toggle_path in proposal.changes,
  );
  if (pending !== undefined) {
    const turnOn = pending.changes[overview.toggle_path] === true;
    return (
      <div className={styles.pending}>
        <p className={styles.pendingTitle}>{turnOn ? t.pendingOn : t.pendingOff}</p>
        <p className={styles.muted}>
          {t.proposedBy} {staffName(pending.proposed_by)} · {formatDateTime(pending.proposed_at)}
        </p>
        <p className={styles.muted}>{pending.reason}</p>
        {hasPermission(session, PERMISSIONS.approvePolicy) ? (
          <SecondSignerApproval
            requestedBy={pending.proposed_by}
            align="start"
            approve={() => approveProposal(pending.proposal_id)}
            invalidate={[policyKeys.overview, networkKeys.overview]}
          />
        ) : null}
      </div>
    );
  }
  if (!hasPermission(session, PERMISSIONS.proposePolicy)) return null;
  return (
    <div className={styles.toggle}>
      <p className={styles.muted}>{t.toggleHint}</p>
      <NetworkToggle enabled={overview.enabled} togglePath={overview.toggle_path} />
    </div>
  );
}

export function NetworkState({ overview }: { overview: NetworkOverview }) {
  return (
    <Card title={t.stateTitle}>
      <div className={styles.body}>
        <SummaryList
          rows={[
            {
              key: "enabled",
              label: t.network,
              value: overview.enabled ? (
                <Badge tone="green" dot>
                  {t.enabled}
                </Badge>
              ) : (
                <Badge tone="neutral" dot>
                  {t.disabled}
                </Badge>
              ),
            },
            { key: "operator", label: t.operator, value: <OperatorBadge overview={overview} /> },
            { key: "policy", label: t.policy, value: overview.policy_version },
            {
              key: "contract",
              label: t.contract,
              value: <code className={styles.code}>{overview.contract}</code>,
            },
            {
              key: "notifications",
              label: t.notifications,
              value: <span className="num">{formatNumber(overview.notifications)}</span>,
            },
          ]}
        />
        <Toggle overview={overview} />
      </div>
    </Card>
  );
}
