"""Innstillingar som blir hugsa mellom kvar gong Froditor startar.

Lagra i ~/.config/froditor/settings.json
"""

import json
import os
from dataclasses import asdict, dataclass, fields

DEFAULT_FONT = "Monospace 12"


@dataclass
class Settings:
    wrap: bool = True
    font: str = DEFAULT_FONT
    width: int = 860
    height: int = 620

    @staticmethod
    def path() -> str:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, "froditor", "settings.json")

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        try:
            with open(cls.path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return settings
        if not isinstance(data, dict):
            return settings
        for field in fields(cls):
            value = data.get(field.name)
            default = getattr(settings, field.name)
            if isinstance(value, type(default)):
                setattr(settings, field.name, value)
        return settings

    def save(self) -> None:
        path = self.path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass  # Innstillingar er ikkje viktige nok til å plage brukaren med feil.
