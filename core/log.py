"""
Sistema de logging con etiquetas por subsistema — DurdrawGUI.

Cada tag activo escribe en logs/{tag}.log (creado junto al ejecutable).
WARNING y ERROR siempre van a logs/warnings.log aunque el tag esté desactivado.

Configuración mediante variable de entorno DURDRAW_LOG:

    DURDRAW_LOG=canvas,cel,tools   activa esos tags además de los defaults
    DURDRAW_LOG=all                activa todos
    DURDRAW_LOG=none               desactiva todo, incluidos los defaults

Tags y activación por defecto:
    app      on   — arranque, configuración, errores fatales
    io       on   — apertura/guardado/exportación de archivos
    theme    on   — inicialización y cambios de tema, variables de entorno Qt
    doc      off  — operaciones de documento: capas, frames
    canvas   off  — renderizado: render_frame, zoom, scroll, overlays
    paint    off  — por-paintEvent (muy verboso: dirty rect, celdas dibujadas)
    cel      off  — cel guides: cómputo de bounds, cambios de datos
    tools    off  — operaciones de herramientas: trazo, pincel, borrador
    history  off  — pila undo/redo: push, pop
    input    off  — eventos de ratón y teclado (muy verboso)

Uso en módulos:
    import core.log as log
    _log = log.get("canvas")        # TagLogger para ese subsistema
    _log.debug("render {w}×{h}")
    _log.info("zoom → {pct}%")
    _log.warning("mensaje")         # siempre emitido aunque tag desactivado
    _log.error("algo malo")         # ídem
"""

import logging
import os
import sys
from pathlib import Path

# ── Directorios ───────────────────────────────────────────────────────────────
_APP_DIR = Path(__file__).parent.parent
_LOG_DIR = _APP_DIR / "logs"

# ── Formatos ──────────────────────────────────────────────────────────────────
_FMT_FILE = logging.Formatter(
    "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(message)s",
    datefmt="%H:%M:%S",
)
_FMT_STDERR = logging.Formatter(
    "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(name)-20s %(message)s",
    datefmt="%H:%M:%S",
)

# ── Tags disponibles y su estado por defecto ──────────────────────────────────
_DEFAULTS: dict[str, bool] = {
    "app":     True,
    "io":      True,
    "theme":   True,
    "doc":     False,
    "canvas":  False,
    "paint":   False,
    "cel":     False,
    "tools":   False,
    "history": False,
    "input":   False,
}


# ── Handler con flush inmediato ───────────────────────────────────────────────
class _FlushHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


# ── TagLogger ─────────────────────────────────────────────────────────────────
class TagLogger:
    """Logger de un subsistema: archivo propio, activación individual."""

    __slots__ = ("tag", "_logger", "_fh", "_on")

    def __init__(self, tag: str, enabled: bool):
        self.tag     = tag
        self._on     = False
        self._fh     = None
        self._logger = logging.getLogger(f"durdraw.{tag}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = True   # WARNING+ llegan al root → warnings.log
        if enabled:
            self._open_file()

    def _open_file(self):
        if self._fh:
            return
        _LOG_DIR.mkdir(exist_ok=True)
        self._fh = _FlushHandler(str(_LOG_DIR / f"{self.tag}.log"),
                                 mode="w", encoding="utf-8")
        self._fh.setLevel(logging.DEBUG)
        self._fh.setFormatter(_FMT_FILE)
        self._logger.addHandler(self._fh)
        self._on = True

    def _close_file(self):
        if self._fh:
            self._logger.removeHandler(self._fh)
            self._fh.close()
            self._fh = None
        self._on = False

    # ── Control de activación ─────────────────────────────────────────────
    def enable(self):
        self._open_file()

    def disable(self):
        self._close_file()

    @property
    def on(self) -> bool:
        return self._on

    # ── Métodos de emisión ────────────────────────────────────────────────
    def debug(self, msg, *a, **kw):
        if self._on:
            self._logger.debug(msg, *a, **kw)

    def info(self, msg, *a, **kw):
        if self._on:
            self._logger.info(msg, *a, **kw)

    def warning(self, msg, *a, **kw):
        # siempre: propagate → root → warnings.log
        self._logger.warning(msg, *a, **kw)

    def error(self, msg, *a, **kw):
        self._logger.error(msg, *a, **kw)

    def exception(self, msg, *a, **kw):
        self._logger.exception(msg, *a, **kw)


# ── Root logger — captura WARNING+ de cualquier tag ───────────────────────────
def _build_root() -> logging.Logger:
    root = logging.getLogger("durdraw")
    if root.handlers:
        return root
    root.setLevel(logging.DEBUG)
    _LOG_DIR.mkdir(exist_ok=True)
    fh = _FlushHandler(str(_LOG_DIR / "warnings.log"), mode="w", encoding="utf-8")
    fh.setLevel(logging.WARNING)
    fh.setFormatter(_FMT_FILE)
    root.addHandler(fh)
    if os.environ.get("DURDRAW_DEBUG"):
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(_FMT_STDERR)
        root.addHandler(sh)
    return root


# ── Resolución de tags activos desde entorno ──────────────────────────────────
def _resolve_enabled() -> dict[str, bool]:
    env = os.environ.get("DURDRAW_LOG", "").strip()
    if env == "all":
        return {t: True for t in _DEFAULTS}
    if env == "none":
        return {t: False for t in _DEFAULTS}
    extras = {t.strip() for t in env.split(",") if t.strip() in _DEFAULTS}
    return {t: (default or t in extras) for t, default in _DEFAULTS.items()}


# ── Inicialización ────────────────────────────────────────────────────────────
_root    = _build_root()
_loggers: dict[str, TagLogger] = {
    tag: TagLogger(tag, enabled)
    for tag, enabled in _resolve_enabled().items()
}


# ── API pública ───────────────────────────────────────────────────────────────
def get(tag: str) -> TagLogger:
    """Devuelve el TagLogger del subsistema. Crea uno dinámico (desactivado) si es nuevo."""
    if tag not in _loggers:
        _loggers[tag] = TagLogger(tag, False)
    return _loggers[tag]


def enable_tag(tag: str):
    """Activa un tag en tiempo de ejecución."""
    get(tag).enable()


def disable_tag(tag: str):
    """Desactiva un tag en tiempo de ejecución."""
    get(tag).disable()


def active_tags() -> list[str]:
    """Tags actualmente habilitados."""
    return sorted(t for t, lg in _loggers.items() if lg.on)


def log_dir() -> Path:
    return _LOG_DIR


# ── Compatibilidad: funciones de módulo → tag 'app' ──────────────────────────
_app = _loggers["app"]

def debug(msg, *a, **kw):     _app.debug(msg, *a, **kw)
def info(msg, *a, **kw):      _app.info(msg, *a, **kw)
def warning(msg, *a, **kw):   _app.warning(msg, *a, **kw)
def error(msg, *a, **kw):     _app.error(msg, *a, **kw)
def exception(msg, *a, **kw): _app.exception(msg, *a, **kw)
