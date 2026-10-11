"""Настройки сервиса: секреты и адреса — из окружения, рабочие значения — из YAML-файлов с версией."""

from pathlib import Path
from typing import Any

import yaml

from shared.errors import ConfigurationError


def load_yaml(path: Path) -> dict[str, Any]:
    """Читает YAML-файл конфигурации; пустой или не-словарь — ошибка конфигурации."""
    if not path.is_file():
        raise ConfigurationError(f"Нет файла конфигурации: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigurationError(f"Файл конфигурации {path} должен содержать словарь")
    return data
