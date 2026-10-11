"""Сводка генератора по межбанковым схемам и ловушкам сети (И4): что видно только через сеть кредиторов."""

from collections import Counter, defaultdict

from world.lenders import OtherLenderWorld
from world.plans import ApplicationPlan
from world.records import CrossLenderSummary, Typology


def _identities(plan: ApplicationPlan) -> list[tuple[str, str]]:
    pairs = [("phone", plan.phone), ("address", plan.address)]
    return [*pairs, ("device", plan.device_id)] if plan.device_id is not None else pairs


def _unlinked(plans: list[ApplicationPlan], cross: list[ApplicationPlan]) -> Counter[Typology]:
    """Заявки из `cross`, ни один телефон, устройство или адрес которых не встречается у другого человека в `plans`."""
    people: dict[tuple[str, str], set[str]] = defaultdict(set)
    for plan in plans:
        for identity in _identities(plan):
            people[identity].add(plan.person.pinfl)
    return Counter(
        plan.typology
        for plan in cross
        if plan.typology is not None and all(people[identity] == {plan.person.pinfl} for identity in _identities(plan))
    )


def _unlinked_in_scheme(cross: list[ApplicationPlan]) -> Counter[Typology]:
    schemes: dict[str | None, list[ApplicationPlan]] = defaultdict(list)
    for plan in cross:
        schemes[plan.scheme_key].append(plan)
    return sum((_unlinked(members, members) for members in schemes.values()), Counter())


def _popular_suppliers(node_plans: list[ApplicationPlan], others: OtherLenderWorld) -> int:
    """Честные поставщики, у которых есть заёмщики у каждого кредитора."""
    lenders: dict[str, set[str]] = defaultdict(set)
    for plan in node_plans:
        if plan.typology is None and plan.program is not None:
            lenders[plan.program.supplier.inn].add(plan.lender)
    for application in others.applications:
        if others.truth[application.id].typology is None and application.supplier_inn is not None:
            lenders[application.supplier_inn].add(application.lender)
    everyone = set().union(*lenders.values()) if lenders else set()
    return sum(1 for seen in lenders.values() if seen == everyone)


def cross_lender_summary(node_plans: list[ApplicationPlan], others: OtherLenderWorld) -> CrossLenderSummary:
    cross = [plan for plan in node_plans if plan.cross_lender]
    schemes = {(plan.typology, plan.scheme_key) for plan in cross}
    schemes |= {(truth.typology, truth.scheme_key) for truth in others.truth.values() if truth.cross_lender}
    fraud_transfers = [
        application.transfer
        for application in others.applications
        if application.transfer is not None and others.truth[application.id].typology is not None
    ]
    return CrossLenderSummary(
        schemes=Counter(typology for typology, _ in schemes if typology is not None),
        node_applications=Counter(plan.typology for plan in cross if plan.typology is not None),
        node_unlinked=_unlinked(node_plans, cross),
        node_unlinked_in_scheme=_unlinked_in_scheme(cross),
        other_applications=Counter(application.lender for application in others.applications),
        other_fraud=Counter(truth.typology for truth in others.truth.values() if truth.typology is not None),
        traps={**others.traps, "popular_suppliers": _popular_suppliers(node_plans, others)},
        issued=sum(1 for application in others.applications if application.issued_at is not None),
        transfers=sum(1 for application in others.applications if application.transfer is not None),
        mule_cards=len({transfer.card for transfer in fraud_transfers}),
        confirmations=sum(1 for application in others.applications if application.confirmation is not None),
    )
