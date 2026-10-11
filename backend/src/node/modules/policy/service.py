"""Реестр версий политики из файлов: действующая версия для решений, любая прежняя — для воспроизведения."""

from pathlib import Path

from node.modules.policy.domain import Policy, PolicyBundle
from node.modules.policy.reasons import CatalogEntry
from shared.config import load_yaml
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConfigurationError, NotFoundError


class PolicyRegistry:
    def __init__(self, bundles: dict[str, PolicyBundle], active_version: str) -> None:
        if active_version not in bundles:
            raise ConfigurationError(f"Нет политики {active_version}")
        self._bundles = bundles
        self.active_version = active_version

    @classmethod
    def from_dir(cls, directory: Path, active_version: str) -> "PolicyRegistry":
        catalogs: dict[str, tuple[dict[str, CatalogEntry], str]] = {}
        for path in sorted(directory.glob("reasons-*.yaml")):
            raw = load_yaml(path)
            entries = {e["code"]: CatalogEntry.model_validate(e) for e in raw["reasons"]}
            catalogs[str(raw["version"])] = (entries, sha256_hex(raw))

        bundles: dict[str, PolicyBundle] = {}
        for path in sorted(directory.glob("policy-*.yaml")):
            raw = load_yaml(path)
            policy = Policy.model_validate(raw)
            if policy.reasons_version not in catalogs:
                raise ConfigurationError(f"{path.name}: нет каталога причин {policy.reasons_version}")
            entries, catalog_hash = catalogs[policy.reasons_version]
            codes = {r.code for r in policy.mandatory_rules} | {r.code for r in policy.product_rules}
            missing = codes - entries.keys()
            if missing:
                raise ConfigurationError(f"{path.name}: коды без описания в каталоге: {sorted(missing)}")
            bundles[policy.version] = PolicyBundle(
                policy=policy,
                catalog=entries,
                policy_hash=sha256_hex(raw),
                catalog_version=policy.reasons_version,
                catalog_hash=catalog_hash,
            )
        if not bundles:
            raise ConfigurationError(f"В {directory} нет файлов политики")
        return cls(bundles, active_version)

    @property
    def active(self) -> PolicyBundle:
        return self._bundles[self.active_version]

    def get(self, version: str) -> PolicyBundle:
        bundle = self._bundles.get(version)
        if bundle is None:
            raise NotFoundError("policy_not_found", f"Версия политики {version} не найдена")
        return bundle
