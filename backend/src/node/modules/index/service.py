"""Сценарии использования индекса: запись появлений и договоров, кого пометить, группы на момент as_of.

Правила обхода, хабов, независимости и границ группы — в SPEC.md; эталонные графы — tests/golden/graphs.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.index import repository
from node.modules.index.domain import (
    APPLICANT,
    Attribute,
    CoordinationSignal,
    GroupView,
    RareLink,
    RoleConcentrations,
    SharedRole,
    burst,
    coordination_signal,
    extract,
    independent_links,
    is_rare_shared,
    link_weight,
    pace_ratio,
    smoothed_pace,
    smoothed_share,
    split_recent,
    window_start,
)
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from shared.contracts.application import ApplicationSnapshot


@dataclass(frozen=True)
class LinkedApplication:
    application_id: UUID
    kinds: tuple[str, ...]


@dataclass(frozen=True)
class ConcentrationParams:
    window_days: int
    prior_weight: float
    prior_windows: float
    helper_window_days: int


def record_version(
    session: Session,
    realm_id: UUID,
    application_id: UUID,
    version: int,
    subject_key: str,
    attributes: list[Attribute],
    snapshot: ApplicationSnapshot,
    occurred_at: datetime,
    received_at: datetime,
) -> None:
    if repository.has_version(session, application_id, version):
        return
    repository.insert_many(
        session,
        [
            {
                "realm_id": realm_id,
                "application_id": application_id,
                "application_version": version,
                "subject_key": subject_key,
                "attr_kind": a.kind,
                "attr_key": a.key,
                "attr_display": a.display,
                "role": a.role,
                "occurred_at": occurred_at,
                "received_at": received_at,
            }
            for a in attributes
        ],
    )
    program = snapshot.program
    if program is not None:
        keys = {a.kind: a.key for a in attributes}
        repository.add_contract(
            session,
            {
                "realm_id": realm_id,
                "application_id": application_id,
                "application_version": version,
                "branch_key": keys["branch"],
                "employee_key": keys.get("employee"),
                "helper_key": keys["helper"],
                "supplier_key": keys["supplier"],
                "item_code": program.item_code,
                "unit": program.unit,
                "district": program.district,
                "unit_price": program.unit_price,
                "received_at": received_at,
            },
        )


def attributes(snapshot: ApplicationSnapshot, secret: bytes) -> list[Attribute]:
    return extract(snapshot, secret)


def linked_for_marking(
    session: Session,
    realm: RealmContext,
    application_id: UUID,
    subject: str,
    attrs: list[Attribute],
    as_of: datetime,
    policy: Policy,
) -> list[LinkedApplication]:
    """Другие заявки, чью картину меняет этот факт: тот же человек или редкий общий атрибут идентичности."""
    since = window_start(as_of, policy.index)
    marking = [a for a in attrs if a.kind in policy.index.marking_kinds and a.role == APPLICANT]
    pairs = [(a.kind, a.key) for a in marking]
    others = repository.subject_counts(session, realm.visible_ids, pairs, since, as_of, exclude_subject=subject)
    relevant = [
        (a.kind, a.key)
        for a in marking
        if a.kind == "pinfl" or is_rare_shared(policy.index, a.kind, others.get((a.kind, a.key), 0) + 1)
    ]
    by_app: dict[UUID, set[str]] = {}
    for app, kind, _key, other_subject in repository.applications_with(
        session, realm.visible_ids, relevant, since, as_of
    ):
        if app == application_id or (kind != "pinfl" and other_subject == subject):
            continue
        by_app.setdefault(app, set()).add(kind)
    return [LinkedApplication(app, tuple(sorted(kinds))) for app, kinds in by_app.items()]


def group_view(
    session: Session, realm: RealmContext, application_id: UUID, as_of: datetime, policy: Policy
) -> GroupView:
    """Группа идентичности — связная компонента по редким общим атрибутам (не дальше max_hops) — и сигналы
    группы координации по ролям заявки."""
    index, kinds = policy.index, policy.index.identity_kinds
    since = window_start(as_of, index)
    rarity: dict[tuple[str, str], int] = {}
    component, frontier = {application_id}, {application_id}
    own_links: list[RareLink] = []
    hops = 0
    while frontier and (index.max_hops is None or hops < index.max_hops):
        attrs = repository.attributes_of(session, realm.visible_ids, frontier, kinds, since, as_of)
        new_pairs = {(kind, key) for _app, kind, key, _display in attrs} - rarity.keys()
        rarity.update(repository.subject_counts(session, realm.visible_ids, new_pairs, since, as_of))
        rare_pairs = {(kind, key) for _app, kind, key, _d in attrs if is_rare_shared(index, kind, rarity[(kind, key)])}
        if application_id in frontier:
            own_links = [
                RareLink(
                    kind=kind, display=display, subjects=rarity[(kind, key)], weight=link_weight(rarity[(kind, key)])
                )
                for app, kind, key, display in attrs
                if app == application_id and (kind, key) in rare_pairs
            ]
        neighbours = {
            app for app, *_ in repository.applications_with(session, realm.visible_ids, rare_pairs, since, as_of)
        }
        frontier = neighbours - component
        component |= frontier
        hops += 1

    seen = repository.first_seen(session, component)
    recent, background, flagged = burst(policy.group, index, list(seen.values()), as_of)
    subjects = repository.subjects_of(session, component)
    return GroupView(
        rare_links=sorted(own_links, key=lambda link: (link.kind, link.display)),
        independent_rare_links=independent_links(own_links),
        group_applications=len(component),
        group_subjects=len(subjects),
        recent_applications=recent,
        background_per_window=background,
        burst=flagged and len(component) > 1,
        shared_roles=_shared_roles(session, realm, application_id, component, policy, since, as_of),
        coordination=_coordination(session, realm, application_id, policy, as_of),
        member_subjects=tuple(sorted(subjects)),
    )


def _prior_pace(
    session: Session, realm: RealmContext, kind: str, since: datetime, until: datetime, windows: float
) -> float:
    """Средний темп одного значения роли этого вида за окно — априорный темп для m-оценки."""
    applications, keys = repository.kind_totals(session, realm.visible_ids, kind, since, until)
    return applications / keys / windows if keys and windows > 0 else 0.0


def _coordination(
    session: Session, realm: RealmContext, application_id: UUID, policy: Policy, as_of: datetime
) -> list[CoordinationSignal]:
    rules = policy.coordination
    if rules is None:
        return []
    index = policy.index
    since = window_start(as_of, index)
    recent_from = as_of - timedelta(days=rules.window_days)
    background_windows = (index.window_days - rules.window_days) / rules.window_days
    signals = []
    for kind, (key, display) in sorted(repository.own_attributes(session, application_id, rules.roles).items()):
        times = repository.role_times(session, realm.visible_ids, kind, key, since, as_of)
        prior = _prior_pace(session, realm, kind, since, recent_from, background_windows)
        signals.append(coordination_signal(rules, index, kind, display, times, prior, as_of))
    return signals


def _shared_roles(
    session: Session,
    realm: RealmContext,
    application_id: UUID,
    component: set[UUID],
    policy: Policy,
    since: datetime,
    as_of: datetime,
) -> list[SharedRole]:
    roles = policy.group.red_when.shared_roles
    rows = repository.attributes_of(session, realm.visible_ids, component, roles, since, as_of)
    own = {(kind, key): display for app, kind, key, display in rows if app == application_id}
    shared: list[SharedRole] = []
    for (kind, key), display in sorted(own.items()):
        others = {app for app, k, kk, _d in rows if (k, kk) == (kind, key) and app != application_id}
        if others:
            shared.append(SharedRole(role=kind, display=display, applications=len(others) + 1))
    return shared


def device_subjects(
    session: Session, realm: RealmContext, application_id: UUID, as_of: datetime, days: int
) -> int | None:
    """Сколько разных людей подавали заявки с устройством этой заявки за days дней."""
    own = repository.own_attributes(session, application_id, ["device"]).get("device")
    if own is None:
        return None
    pair = ("device", own[0])
    counts = repository.subject_counts(session, realm.visible_ids, [pair], as_of - timedelta(days=days), as_of)
    return counts.get(pair, 0)


def comparable_prices(
    session: Session,
    realm: RealmContext,
    application_id: UUID,
    snapshot: ApplicationSnapshot,
    levels: list[tuple[bool, int]],
    as_of: datetime,
) -> list[list[int]]:
    """Цены сравнимых договоров по уровням (только район?, окно в днях), от узкого к широкому."""
    program = snapshot.program
    if program is None:
        return []
    return [
        repository.comparable_prices(
            session,
            realm.visible_ids,
            application_id,
            program.item_code,
            program.unit,
            program.district if district_only else None,
            as_of - timedelta(days=days),
            as_of,
        )
        for district_only, days in levels
    ]


def concentrations(
    session: Session, realm: RealmContext, application_id: UUID, as_of: datetime, params: ConcentrationParams
) -> RoleConcentrations:
    """Концентрации ролей программной заявки: поставщик в филиале, сотрудник, помощник (Блок 3, зона 3)."""
    own = repository.own_attributes(session, application_id, ["branch", "employee", "helper", "supplier"])
    if "supplier" not in own:
        return RoleConcentrations()
    ids, since = realm.visible_ids, as_of - timedelta(days=params.window_days)
    supplier = own["supplier"][0]
    supplier_ratio = hhi = employee_ratio = None
    if "branch" in own:
        branch = own["branch"][0]
        at_branch = repository.contract_counts(session, ids, "supplier_key", since, as_of, branch_key=branch)
        total_branch = sum(at_branch.values())
        everywhere = repository.contract_counts(session, ids, "supplier_key", since, as_of)
        global_share = everywhere.get(supplier, 0) / max(sum(everywhere.values()), 1)
        if global_share > 0 and total_branch:
            share = smoothed_share(at_branch.get(supplier, 0), total_branch, global_share, params.prior_weight)
            supplier_ratio = round(share / global_share, 4)
            hhi = round(sum((c / total_branch) ** 2 for c in at_branch.values()), 4)
        if "employee" in own:
            staff = repository.contract_counts(session, ids, "employee_key", since, as_of, branch_key=branch)
            if staff:
                prior = 1 / len(staff)
                count = staff.get(own["employee"][0], 0)
                share = smoothed_share(count, sum(staff.values()), prior, params.prior_weight)
                employee_ratio = round(share / prior, 4)
    helper_burst = helper_supplier = None
    if "helper" in own:
        helper = own["helper"][0]
        times = repository.role_times(session, ids, "helper", helper, since, as_of)
        recent, earlier = split_recent(times, as_of, params.helper_window_days, params.window_days)
        windows = (params.window_days - params.helper_window_days) / params.helper_window_days
        recent_from = as_of - timedelta(days=params.helper_window_days)
        prior = _prior_pace(session, realm, "helper", since, recent_from, windows)
        helper_burst = pace_ratio(recent, smoothed_pace(earlier, windows, prior, params.prior_windows))
        by_supplier = repository.contract_counts(session, ids, "supplier_key", since, as_of, helper_key=helper)
        helper_supplier = round(by_supplier.get(supplier, 0) / max(sum(by_supplier.values()), 1), 4)
    return RoleConcentrations(
        supplier_ratio=supplier_ratio,
        branch_supplier_hhi=hhi,
        employee_ratio=employee_ratio,
        helper_burst_ratio=helper_burst,
        helper_supplier_share=helper_supplier,
    )
