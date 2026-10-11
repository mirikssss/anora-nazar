"""Ключ подписи узла: python -m shared.keys <файл закрытого ключа> <файл публичного ключа>.

Закрытый ключ остаётся у узла; публичный получают те, кто проверяет подписи: АБС и якорь журнала.
Существующий ключ не перезаписывается.
"""

import sys
from pathlib import Path

from shared.crypto.signing import export_public_key, generate_key_file


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("Использование: python -m shared.keys <закрытый ключ> <публичный ключ>")
    private, public = Path(argv[0]), Path(argv[1])
    generate_key_file(private)
    export_public_key(private, public)


if __name__ == "__main__":
    main(sys.argv[1:])
