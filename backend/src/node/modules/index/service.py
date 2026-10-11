"""Сценарии использования модуля: запись появлений, кого пометить, агрегаты группы на момент as_of."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.index import repository
from node.modules.index.domain import (
    APPLICANT,
    Attribute,
    GroupView,
    RareLink,
    SharedRole,
    burst,
    extract,
    independent_links,
    is_rare_shared,
    link_weight,
    window_start,
)
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from shared.contracts.application import ApplicationSnapshot


@dataclass(frozen=True)
class LinkedApplication:
    application_id: UUID
    kinds: tuple[str, ...]


def record_version(
    session: Session,
    realm_id: UUID,
    application_id: UUID,
    version: int,
    subject_key: str,
    attributes: list[Attribute],
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
    """Связная компонента по редким общим атрибутам идентичности и её агрегаты на момент as_of."""
    index, kinds = policy.index, policy.index.identity_kinds
    since = window_start(as_of, index)
    rarity: dict[tuple[str, str], int] = {}
    component, frontier = {application_id}, {application_id}
    own_links: list[RareLink] = []
    while frontier:
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

    seen = repository.first_seen(session, component)
    recent, background, flagged = burst(policy.group, index, list(seen.values()), as_of)
    return GroupView(
        rare_links=sorted(own_links, key=lambda link: (link.kind, link.display)),
        independent_rare_links=independent_links(own_links),
        group_applications=len(component),
        group_subjects=len(repository.subjects_of(session, component)),
        recent_applications=recent,
        background_per_window=background,
        burst=flagged and len(component) > 1,
        shared_roles=_shared_roles(session, realm, application_id, component, policy, since, as_of),
    )


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
