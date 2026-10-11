"""Реестр версий политики: файлы с версией и версии, утверждённые вторым подписантом в контуре.

Действующая политика контура — последняя утверждённая в песочнице, иначе в общем мире, иначе файловая.
Любая прежняя версия доступна для воспроизведения решения.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.audit import service as audit
from node.modules.policy import repository
from node.modules.policy.domain import Policy, PolicyBundle, apply_changes
from node.modules.policy.models import PolicyProposal, PolicyVersion
from node.modules.policy.reasons import CatalogEntry
from node.modules.realms.domain import RealmContext
from shared.config import load_yaml
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConfigurationError, ConflictError, ForbiddenError, NotFoundError, ValidationFailedError


class PolicyRegistry:
    def __init__(
        self,
        bundles: dict[str, PolicyBundle],
        catalogs: dict[str, tuple[dict[str, CatalogEntry], str]],
        raw: dict[str, dict[str, Any]],
        active_version: str,
    ) -> None:
        if active_version not in bundles:
            raise ConfigurationError(f"Нет политики {active_version}")
        self._bundles, self._catalogs, self._raw = bundles, catalogs, raw
        self.active_version = active_version

    @classmethod
    def from_dir(cls, directory: Path, active_version: str) -> "PolicyRegistry":
        catalogs: dict[str, tuple[dict[str, CatalogEntry], str]] = {}
        for path in sorted(directory.glob("reasons-*.yaml")):
            raw = load_yaml(path)
            entries = {e["code"]: CatalogEntry.model_validate(e) for e in raw["reasons"]}
            catalogs[str(raw["version"])] = (entries, sha256_hex(raw))
        bundles: dict[str, PolicyBundle] = {}
        sources: dict[str, dict[str, Any]] = {}
        for path in sorted(directory.glob("policy-*.yaml")):
            raw = load_yaml(path)
            bundle = _bundle(raw, catalogs, path.name)
            bundles[bundle.policy.version] = bundle
            sources[bundle.policy.version] = raw
        if not bundles:
            raise ConfigurationError(f"В {directory} нет файлов политики")
        return cls(bundles, catalogs, sources, active_version)

    @property
    def active(self) -> PolicyBundle:
        return self._bundles[self.active_version]

    def raw(self, version: str) -> dict[str, Any]:
        found = self._raw.get(version)
        if found is None:
            raise NotFoundError("policy_not_found", f"Версия политики {version} не найдена")
        return found

    def _from_db(self, row: PolicyVersion) -> PolicyBundle:
        cached = self._bundles.get(row.version)
        if cached is None:
            cached = _bundle(row.content, self._catalogs, row.version)
            self._bundles[row.version], self._raw[row.version] = cached, row.content
        return cached

    def get(self, version: str, session: Session | None = None) -> PolicyBundle:
        bundle = self._bundles.get(version)
        if bundle is None and session is not None:
            row = repository.version(session, version)
            bundle = None if row is None else self._from_db(row)
        if bundle is None:
            raise NotFoundError("policy_not_found", f"Версия политики {version} не найдена")
        return bundle

    def for_realm(self, session: Session, realm: RealmContext) -> PolicyBundle:
        row = repository.latest_for(session, realm.visible_ids, realm.id)
        return self.active if row is None else self._from_db(row)


def _bundle(raw: dict[str, Any], catalogs: dict[str, tuple[dict[str, CatalogEntry], str]], name: str) -> PolicyBundle:
    policy = Policy.model_validate(raw)
    if policy.reasons_version not in catalogs:
        raise ConfigurationError(f"{name}: нет каталога причин {policy.reasons_version}")
    entries, catalog_hash = catalogs[policy.reasons_version]
    codes = {r.code for r in policy.mandatory_rules} | {r.code for r in policy.product_rules}
    missing = codes - entries.keys()
    if missing:
        raise ConfigurationError(f"{name}: коды без описания в каталоге: {sorted(missing)}")
    return PolicyBundle(
        policy=policy,
        catalog=entries,
        policy_hash=sha256_hex(raw),
        catalog_version=policy.reasons_version,
        catalog_hash=catalog_hash,
    )


def propose(
    session: Session,
    registry: PolicyRegistry,
    realm: RealmContext,
    changes: dict[str, float],
    reason: str,
    staff: str,
    editable: list[str],
    now: datetime,
) -> PolicyProposal:
    """Предложение порога: только разрешённые пути; проверяется сразу, утверждает другой сотрудник."""
    base = registry.for_realm(session, realm)
    try:
        apply_changes(registry.raw(base.policy.version), changes, editable, f"{base.policy.version}+check")
    except ValueError as exc:
        raise ValidationFailedError("invalid_policy_change", str(exc)) from exc
    proposal = PolicyProposal(
        id=uuid4(),
        realm_id=realm.id,
        base_version=base.policy.version,
        changes=changes,
        reason=reason,
        proposed_by=staff,
        proposed_at=now,
        approved_by=None,
        approved_at=None,
        resulting_version=None,
    )
    repository.add(session, proposal)
    session.flush()
    audit.append(
        session,
        realm.id,
        "policy.proposed",
        {"proposal_id": str(proposal.id), "base_version": base.policy.version, "changes": changes, "by": staff},
        now,
    )
    return proposal


def approve(
    session: Session,
    registry: PolicyRegistry,
    realm: RealmContext,
    proposal_id: UUID,
    staff: str,
    editable: list[str],
    now: datetime,
) -> PolicyProposal:
    """Второй подписант — другой сотрудник; утверждённая версия действует только в этом контуре."""
    proposal = repository.proposal_for_update(session, proposal_id)
    if proposal is None or proposal.realm_id != realm.id:
        raise NotFoundError("proposal_not_found", "Предложение не найдено")
    if proposal.approved_at is not None:
        raise ConflictError("proposal_already_approved", "Предложение уже утверждено")
    if proposal.proposed_by == staff:
        raise ForbiddenError("second_signer_required", "Подтверждает другой сотрудник: нужен второй подписант")
    version = f"{proposal.base_version}+{proposal.id.hex[:8]}"
    content = apply_changes(registry.raw(proposal.base_version), proposal.changes, editable, version)
    repository.add(
        session,
        PolicyVersion(
            version=version,
            realm_id=realm.id,
            base_version=proposal.base_version,
            content=content,
            content_hash=sha256_hex(content),
            proposal_id=proposal.id,
            created_at=now,
        ),
    )
    proposal.approved_by, proposal.approved_at, proposal.resulting_version = staff, now, version
    audit.append(
        session,
        realm.id,
        "policy.approved",
        {"proposal_id": str(proposal.id), "version": version, "by": staff, "proposed_by": proposal.proposed_by},
        now,
    )
    return proposal


def overview(
    session: Session, registry: PolicyRegistry, realm: RealmContext
) -> tuple[PolicyBundle, list[PolicyProposal]]:
    return registry.for_realm(session, realm), repository.proposals(session, realm.id)
