"""Gestor de atajos de teclado — configurables por el usuario."""

import json
import os
from pathlib import Path

_CFG_DIR  = Path(os.path.expanduser("~/.config/durdrawgui"))
_SC_FILE  = _CFG_DIR / "shortcuts.json"

# (etiqueta, tecla_por_defecto)
ACTIONS: dict[str, tuple[str, str]] = {
    # ── Herramientas ──────────────────────────────────────────────────
    "tool_pencil":       ("Lápiz",                   "B"),
    "tool_eraser":       ("Borrador",                "E"),
    "tool_eyedropper":   ("Cuentagotas",             "I"),
    "tool_fill":         ("Relleno",                 "G"),
    "tool_selection":    ("Selección",               "S"),
    "tool_line":         ("Línea",                   "L"),
    "tool_rect":         ("Rectángulo",              "R"),
    "tool_ellipse":      ("Elipse",                  "O"),
    "swap_colors":       ("Intercambiar colores",    "X"),
    # ── Vista ─────────────────────────────────────────────────────────
    "zoom_in":           ("Acercar",                 "Ctrl+="),
    "zoom_out":          ("Alejar",                  "Ctrl+-"),
    "zoom_reset":        ("Zoom 1:1 (menú)",         "Ctrl+0"),
    "zoom_reset_1":      ("Zoom 1:1 (tecla 1)",      "1"),
    "center_view":       ("Centrar lienzo",          "Ctrl+Home"),
    "minimap_toggle":    ("Mostrar/ocultar minimapa", "M"),
    # ── Edición ───────────────────────────────────────────────────────
    "undo":              ("Deshacer",                "Ctrl+Z"),
    "redo":              ("Rehacer",                 "Ctrl+Y"),
    "redo_alt":          ("Rehacer (alternativo)",   "Ctrl+Shift+Z"),
    "copy":              ("Copiar",                  "Ctrl+C"),
    "cut":               ("Cortar",                  "Ctrl+X"),
    "paste":             ("Pegar",                   "Ctrl+V"),
    "select_all":        ("Seleccionar todo",        "Ctrl+A"),
    "deselect":          ("Deseleccionar (menú)",    "Ctrl+D"),
    "deselect_esc":      ("Deseleccionar (Esc)",     "Escape"),
    "clear_selection":   ("Borrar selección",        "Delete"),
    # ── Archivo ───────────────────────────────────────────────────────
    "file_new":          ("Nuevo lienzo…",           "Ctrl+N"),
    "file_open":         ("Abrir…",                  "Ctrl+O"),
    "file_save":         ("Guardar…",                "Ctrl+S"),
    "file_quit":         ("Salir",                   "Ctrl+Q"),
    # ── Frames ────────────────────────────────────────────────────────
    "frame_new":         ("Nuevo frame",             "Alt+N"),
    "frame_duplicate":   ("Duplicar frame",          "Alt+D"),
    "frame_delete":      ("Eliminar frame",          "Alt+C"),
    "frame_prev":        ("Frame anterior",          "Left"),
    "frame_next":        ("Frame siguiente",         "Right"),
    "frame_first":       ("Ir al primer frame",      "Home"),
    "frame_last":        ("Ir al último frame",      "End"),
    "play_toggle":       ("Reproducir / Pausar",     "Return"),
}


class ShortcutManager:
    """Mantiene la asignación action_id → tecla (con persistencia JSON)."""

    def __init__(self):
        self._keys: dict[str, str] = {k: v[1] for k, v in ACTIONS.items()}
        self._load()

    # ── Consulta / modificación ────────────────────────────────────────

    def key(self, action_id: str) -> str:
        return self._keys.get(action_id, ACTIONS.get(action_id, ("", ""))[1])

    def label(self, action_id: str) -> str:
        return ACTIONS.get(action_id, (action_id, ""))[0]

    def set_key(self, action_id: str, key_str: str):
        self._keys[action_id] = key_str

    def reset(self, action_id: str):
        self._keys[action_id] = ACTIONS[action_id][1]

    def reset_all(self):
        for k, v in ACTIONS.items():
            self._keys[k] = v[1]

    # ── Persistencia ──────────────────────────────────────────────────

    def _load(self):
        if _SC_FILE.exists():
            try:
                with open(_SC_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    if k in self._keys:
                        self._keys[k] = v
            except Exception:
                pass

    def save(self):
        _CFG_DIR.mkdir(parents=True, exist_ok=True)
        # sólo guardar los que difieren del default
        overrides = {k: v for k, v in self._keys.items()
                     if v != ACTIONS.get(k, ("", v))[1]}
        with open(_SC_FILE, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
