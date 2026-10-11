// Заявка в конвейере: условия, итоги обязательных проверок и ответ узла с действиями банка.
import { Link } from "react-router";

import { lastDecision, snapshotView, type Application } from "@/entities/application";
import { hasPermission, useSession } from "@/entities/session";
import { ApplicationActions } from "@/features/application-actions";
import { PERMISSIONS } from "@/shared/config/permissions";
import { IconDecision, IconForward } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { formatSum } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/Badge";
import { Card } from "@/shared/ui/Card";
import { StateMessage } from "@/shared/ui/StateMessage";
import { SummaryList, type SummaryRow } from "@/shared/ui/SummaryList";
import { DecisionCard } from "@/widgets/decision-card/DecisionCard";

import styles from "./ApplicationDetail.module.css";

const t = ru.application;

function termsRows(application: Application): SummaryRow[] {
  const view = snapshotView(application);
  const value = (text: string | number | null) => (text === null ? ru.common.none : text);
  const rows: SummaryRow[] = [
    { key: "channel", label: t.channel, value: label(ru.channels, application.channel) },
    { key: "amount", label: t.amount, value: view.amount !== null ? formatSum(view.amount) : ru.common.none },
    {
      key: "term",
      label: t.term,
      value: view.termMonths !== null ? `${String(view.termMonths)} ${ru.common.months}` : ru.common.none,
    },
    { key: "pinfl", label: t.pinfl, value: value(view.pinfl) },
    { key: "phone", label: t.phone, value: value(view.phone) },
    { key: "device", label: t.device, value: value(view.deviceId) },
    { key: "branch", label: t.branch, value: value(view.branchId) },
  ];
  if (view.account !== null) rows.push({ key: "account", label: t.account, value: view.account });
  if (view.program !== null) {
    rows.push({ key: "supplier", label: t.supplier, value: String(view.program.supplier_inn) });
    rows.push({ key: "item", label: t.item, value: String(view.program.item_code) });
  }
  if (view.mandatory !== null) {
    const checks = view.mandatory;
    rows.push({
      key: "checks",
      label: t.mandatoryChecks,
      value: [
        `${t.selfBan}: ${label(ru.checks.self_ban, String(checks.self_ban))}`,
        `${t.bureau}: ${label(ru.checks.bureau, String(checks.bureau))}`,
        `${t.biometry}: ${label(ru.checks.biometry, String(checks.biometry))}`,
        `${t.phoneOwner}: ${checks.phone_owner_match === true ? ru.common.yes : ru.common.no}`,
      ].join(" · "),
    });
  }
  return rows;
}

export function ApplicationDetail({ application }: { application: Application | null }) {
  const session = useSession();
  if (application === null) return <StateMessage title={t.select} />;
  const decision = lastDecision(application);
  const canOpenDecision = hasPermission(session, PERMISSIONS.viewDecisions) && decision?.decisionId != null;
  return (
    <Card
      title={application.id}
      subtitle={`${t.version} ${String(application.version)} · ${label(ru.applicationStatuses, application.status)}`}
      actions={
        application.node_state !== null ? (
          <Badge tone="orange">{label(ru.nodeStates, application.node_state)}</Badge>
        ) : undefined
      }
    >
      <div className={styles.body}>
        {decision !== null ? (
          <DecisionCard
            result={decision}
            point={decision.point}
            holds={decision.holds}
            marked={decision.marked}
            actions={
              <div className={styles.links}>
                {canOpenDecision ? (
                  <Link to={`/decisions/${String(decision.decisionId)}`} className={styles.link}>
                    <IconDecision size={16} aria-hidden />
                    {t.openDecision}
                  </Link>
                ) : null}
                {hasPermission(session, PERMISSIONS.executeCoreBanking) ? (
                  <Link to={`/bank/core-banking?application=${application.id}`} className={styles.link}>
                    {t.toCoreBanking}
                    <IconForward size={16} aria-hidden />
                  </Link>
                ) : null}
              </div>
            }
          />
        ) : null}
        <ApplicationActions application={application} />
        <section className={styles.terms}>
          <h3 className={styles.heading}>{t.terms}</h3>
          <SummaryList rows={termsRows(application)} />
        </section>
      </div>
    </Card>
  );
}
