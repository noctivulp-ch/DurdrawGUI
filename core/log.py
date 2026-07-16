"""
Sistema de logging centralizado para DurdrawGUI.

Escribe a durdrawgui.log junto al directorio raíz de la app, con flush
inmediato después de cada línea para poder monitorear en tiempo real:

    tail -f /ruta/a/DurdrawGUI/durdrawgui.log

Variable de entorno opcional:
    DURDRAW_DEBUG=1   →  duplica la salida a stderr
"""

import logging
import os
import sys

_APP_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH  = os.path.join(_APP_DIR, "durdrawgui.log")

_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(module)s: %(message)s",
    datefmt="%H:%M:%S",
)


class _FlushHandler(logging.FileHandler):
    """FileHandler con flush inmediato — garantiza salida en tiempo real."""
    def emit(self, record):
        super().emit(record)
        self.flush()


def _build() -> logging.Logger:
    log = logging.getLogger("durdraw")
    if log.handlers:
        return log          # ya inicializado (import doble)
    log.setLevel(logging.DEBUG)

    fh = _FlushHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FMT)
    log.addHandler(fh)

    if os.environ.get("DURDRAW_DEBUG"):
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(_FMT)
        log.addHandler(sh)

    return log


_root = _build()


# ── API pública ───────────────────────────────────────────────────────────────

def get(name: str = "") -> logging.Logger:
    """Logger hijo del root 'durdraw'. Usar en módulos: log = core.log.get(__name__)"""
    return _root.getChild(name) if name else _root

def debug(msg, *a, **kw):    _root.debug(msg, *a, **kw)
def info(msg, *a, **kw):     _root.info(msg, *a, **kw)
def warning(msg, *a, **kw):  _root.warning(msg, *a, **kw)
def error(msg, *a, **kw):    _root.error(msg, *a, **kw)

def exception(msg, *a, **kw):
    _root.exception(msg, *a, **kw)   # incluye traceback completo
