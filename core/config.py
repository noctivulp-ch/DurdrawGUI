"""Configuración persistente de la aplicación."""

import json
import os
from pathlib import Path

_CFG_DIR  = Path(os.path.expanduser("~/.config/durdrawgui"))
_CFG_FILE = _CFG_DIR / "prefs.json"

_DEFAULTS: dict[str, object] = {
    "minimap_visible": False,
    "minimap_corner":  "TR",   # TL | TR | BL | BR
    "minimap_max_w":   240,
    "minimap_max_h":   160,
    "canvas_font":     "DejaVu Sans Mono",
    "theme":           "dark",  # system | dark | light
}


class AppConfig:
    """Preferencias de la aplicación con persistencia JSON."""

    def __init__(self):
        self._data: dict[str, object] = dict(_DEFAULTS)
        self._load()

    def get(self, key: str, default=None):
        return self._data.get(key, _DEFAULTS.get(key, default))

    def set(self, key: str, value):
        self._data[key] = value

    def _load(self):
        if _CFG_FILE.exists():
            try:
                with open(_CFG_FILE, encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def save(self):
        _CFG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
