"""Подпись Ed25519: разрешения и контрольные точки журнала. В демо ключ — файл, в целевом — HSM."""

import base64
import hashlib
from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from shared.crypto.canonical_json import canonical_bytes
from shared.errors import ConfigurationError


def key_id_of(verify_key: VerifyKey) -> str:
    return hashlib.sha256(bytes(verify_key)).hexdigest()[:16]


class Signer:
    def __init__(self, signing_key: SigningKey) -> None:
        self._key = signing_key
        self.verify_key = signing_key.verify_key
        self.key_id = key_id_of(self.verify_key)

    @classmethod
    def from_file(cls, path: Path) -> "Signer":
        """Файл ключа — 32 байта seed в base64. Нет файла — сервис не стартует: без подписи нет решения."""
        if not path.is_file():
            raise ConfigurationError(f"Нет файла ключа подписи: {path}")
        seed = base64.b64decode(path.read_text(encoding="ascii").strip())
        return cls(SigningKey(seed))

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(bytes(self.verify_key)).decode("ascii")

    def sign(self, payload: Any) -> str:
        signature = self._key.sign(canonical_bytes(payload)).signature
        return base64.b64encode(signature).decode("ascii")


class Verifier:
    def __init__(self, public_key_b64: str) -> None:
        self._key = VerifyKey(base64.b64decode(public_key_b64))
        self.key_id = key_id_of(self._key)

    def is_valid(self, payload: Any, signature_b64: str) -> bool:
        try:
            self._key.verify(canonical_bytes(payload), base64.b64decode(signature_b64))
        except (BadSignatureError, ValueError):
            return False
        return True


def generate_key_file(path: Path) -> None:
    """Создаёт новый ключ, если файла ещё нет. Существующий ключ не перезаписывается."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = bytes(SigningKey.generate())
    path.write_text(base64.b64encode(seed).decode("ascii"), encoding="ascii")
    path.chmod(0o600)


def export_public_key(private_path: Path, public_path: Path) -> None:
    """Публичный ключ — тем, кто проверяет подписи узла: АБС банка и якорю журнала."""
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(Signer.from_file(private_path).public_key_b64, encoding="ascii")


def read_public_key(path: Path) -> Verifier:
    if not path.is_file():
        raise ConfigurationError(f"Нет файла публичного ключа узла: {path}")
    return Verifier(path.read_text(encoding="ascii").strip())
