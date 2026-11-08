"""Gestor de atajos de teclado — configurables por el usuario, hasta 2 combinaciones por acción."""

import json

from core.config import _resolve_config_dir

_CFG_DIR  = _resolve_config_dir()   # respeta --config-dir / DURDRAW_CONFIG_DIR
_SC_FILE  = _CFG_DIR / "shortcuts.json"

CATEGORY_ORDER = [
    "Herramientas", "Vista", "Edición", "Archivo", "Exportar",
    "Frame", "Capas", "Dibujo por teclado", "Ratón y tableta",
]

# (etiqueta, tecla_primaria_por_defecto, tecla_secundaria_por_defecto, categoría)
# Ambas teclas son opcionales — "" significa sin asignar.
#
# Convención de namespace: las teclas sueltas (sin modificador) y las
# flechas/Home/End/Return/Delete/Escape/Space están reservadas para
# herramientas, navegación y el modo "Dibujo por teclado". Toda acción de
# menú (guardar, capas, exportar, alternar rejilla/color…) usa combinaciones
# con Ctrl/Alt/Shift para no competir con ese espacio — así el modo de
# dibujo puede tomar las teclas sueltas sin chocar con el resto: al activarse
# desactiva temporalmente las acciones sueltas de este namespace (ver
# App._KB_MODE_GATED_ACTIONS) y las combinaciones con modificador siguen
# funcionando con normalidad.
ACTIONS: dict[str, tuple[str, str, str, str]] = {
    # ── Herramientas ──────────────────────────────────────────────────
    "tool_pencil":       ("Lápiz",                   "B", "", "Herramientas"),
    "tool_eraser":       ("Borrador",                "E", "", "Herramientas"),
    "tool_eyedropper":   ("Cuentagotas",             "I", "", "Herramientas"),
    "tool_fill":         ("Relleno",                 "G", "", "Herramientas"),
    "tool_selection":    ("Selección",               "S", "", "Herramientas"),
    "tool_line":         ("Línea",                   "L", "", "Herramientas"),
    "tool_rect":         ("Rectángulo",              "R", "", "Herramientas"),
    "tool_ellipse":      ("Elipse",                  "O", "", "Herramientas"),
    "swap_colors":       ("Intercambiar colores",    "X", "", "Herramientas"),
    # ── Vista ─────────────────────────────────────────────────────────
    "zoom_in":           ("Acercar",                 "Ctrl+=", "", "Vista"),
    "zoom_out":          ("Alejar",                  "Ctrl+-", "", "Vista"),
    "zoom_reset":        ("Zoom 1:1",                "Ctrl+0", "1", "Vista"),
    "center_view":       ("Centrar lienzo",          "Ctrl+Home", "", "Vista"),
    "minimap_toggle":    ("Mostrar/ocultar minimapa", "M", "", "Vista"),
    "toggle_grid":       ("Mostrar/ocultar rejilla", "Ctrl+G", "", "Vista"),
    "toggle_color_mode": ("Modo 256 colores",        "Ctrl+Shift+M", "", "Vista"),
    # ── Edición ───────────────────────────────────────────────────────
    "undo":              ("Deshacer",                "Ctrl+Z", "", "Edición"),
    "redo":              ("Rehacer",                 "Ctrl+Y", "Ctrl+Shift+Z", "Edición"),
    "copy":              ("Copiar",                  "Ctrl+C", "", "Edición"),
    "cut":               ("Cortar",                  "Ctrl+X", "", "Edición"),
    "paste":             ("Pegar",                   "Ctrl+V", "", "Edición"),
    "select_all":        ("Seleccionar todo",        "Ctrl+A", "", "Edición"),
    "deselect":          ("Deseleccionar",           "Ctrl+D", "Escape", "Edición"),
    "clear_selection":   ("Borrar selección",        "Delete", "", "Edición"),
    # ── Archivo ───────────────────────────────────────────────────────
    "file_new":          ("Nuevo lienzo…",           "Ctrl+N", "", "Archivo"),
    "file_open":         ("Abrir…",                  "Ctrl+O", "", "Archivo"),
    "file_save":         ("Guardar",                 "Ctrl+S", "", "Archivo"),
    "file_save_as":      ("Guardar como…",           "Ctrl+Shift+S", "", "Archivo"),
    "preferences":       ("Preferencias…",           "Ctrl+,", "", "Archivo"),
    "file_quit":         ("Salir",                   "Ctrl+Q", "", "Archivo"),
    # ── Exportar ──────────────────────────────────────────────────────
    "export_ansi":       ("Exportar ANSI…",          "Ctrl+Alt+A", "", "Exportar"),
    "export_png":        ("Exportar PNG…",           "Ctrl+Alt+P", "", "Exportar"),
    "export_jpeg":       ("Exportar JPEG…",          "", "", "Exportar"),
    "export_gif":        ("Exportar GIF animado…",   "Ctrl+Alt+G", "", "Exportar"),
    "export_mp4":        ("Exportar MP4…",           "Ctrl+Alt+M", "", "Exportar"),
    # ── Frames ────────────────────────────────────────────────────────
    "frame_new":         ("Nuevo frame",             "Alt+N", "", "Frame"),
    "frame_duplicate":   ("Duplicar frame",          "Alt+D", "", "Frame"),
    "frame_delete":      ("Eliminar frame",          "Alt+C", "", "Frame"),
    "frame_prev":        ("Frame anterior",          "Left", "", "Frame"),
    "frame_next":        ("Frame siguiente",         "Right", "", "Frame"),
    "frame_first":       ("Ir al primer frame",      "Home", "", "Frame"),
    "frame_last":        ("Ir al último frame",      "End", "", "Frame"),
    "play_toggle":       ("Reproducir / Pausar",     "Return", "", "Frame"),
    # ── Capas ─────────────────────────────────────────────────────────
    "layer_new":         ("Nueva capa",              "Ctrl+Shift+N", "", "Capas"),
    "layer_delete":      ("Eliminar capa",           "Ctrl+Shift+Delete", "", "Capas"),
    "layer_move_up":     ("Subir capa",              "Ctrl+Shift+Up", "", "Capas"),
    "layer_move_down":   ("Bajar capa",              "Ctrl+Shift+Down", "", "Capas"),
    # ── Dibujo por teclado ──────────────────────────────────────────────
    # Leídas en vivo por AsciiCanvas mientras el modo está activo — no son
    # QAction globales, así que no chocan con nada del resto de la tabla.
    # Con modificador a propósito: como QAction de ventana funciona sin
    # importar qué widget tenga el foco (igual que Ctrl+S, etc.) — un
    # secundario en Tab suelto degradaría a "solo si el canvas ya tiene
    # foco" (ver ui/canvas.py::event), así que se descartó.
    "kb_draw_toggle":    ("Activar/desactivar modo cursor de teclado", "Ctrl+Tab", "", "Dibujo por teclado"),
    "kb_cursor_up":      ("Cursor: mover arriba",     "Up",    "", "Dibujo por teclado"),
    "kb_cursor_down":    ("Cursor: mover abajo",      "Down",  "", "Dibujo por teclado"),
    "kb_cursor_left":    ("Cursor: mover izquierda",  "Left",  "", "Dibujo por teclado"),
    "kb_cursor_right":   ("Cursor: mover derecha",    "Right", "", "Dibujo por teclado"),
    "kb_pan_up":         ("Lienzo: desplazar arriba",    "W", "", "Dibujo por teclado"),
    "kb_pan_down":       ("Lienzo: desplazar abajo",     "S", "", "Dibujo por teclado"),
    "kb_pan_left":       ("Lienzo: desplazar izquierda", "A", "", "Dibujo por teclado"),
    "kb_pan_right":      ("Lienzo: desplazar derecha",   "D", "", "Dibujo por teclado"),
    "kb_execute":        ("Ejecutar herramienta activa en el cursor", "Space", "", "Dibujo por teclado"),
    "kb_erase":          ("Borrar celda bajo el cursor",  "Q", "", "Dibujo por teclado"),
    "kb_toggle_fgbg":    ("Alternar edición color frente/fondo", "E", "", "Dibujo por teclado"),
    "kb_pick_color":     ("Recoger color/carácter bajo el cursor", "F", "", "Dibujo por teclado"),
    "kb_color_up":       ("Paleta: color de la fila anterior",   "I", "", "Dibujo por teclado"),
    "kb_color_down":     ("Paleta: color de la fila siguiente",  "K", "", "Dibujo por teclado"),
    "kb_color_left":     ("Paleta: color anterior",              "J", "", "Dibujo por teclado"),
    "kb_color_right":    ("Paleta: color siguiente",             "L", "", "Dibujo por teclado"),
    # Selección de carácter: las teclas 1-9,0 (fila de 10, posición fija —
    # no configurables) eligen la celda dentro de la fila activa del grupo
    # de caracteres actual; ver KeyboardInput._handle_kb_draw_key (ui/input/keyboard.py).
    "kb_char_row_up":    ("Caracteres: fila anterior",    "Ctrl+Up",    "", "Dibujo por teclado"),
    "kb_char_row_down":  ("Caracteres: fila siguiente",   "Ctrl+Down",  "", "Dibujo por teclado"),
    "kb_char_group_prev":("Caracteres: grupo/pestaña anterior", "Ctrl+Left",  "", "Dibujo por teclado"),
    "kb_char_group_next":("Caracteres: grupo/pestaña siguiente","Ctrl+Right", "", "Dibujo por teclado"),
    # ── Ratón y tableta ──────────────────────────────────────────────────
    # Los bindings de esta categoría son botones de ratón/tableta, formato
    # "Mouse:<Qt.MouseButton.name>" (ej. "Mouse:RightButton",
    # "Mouse:ExtraButton5"), capturados con clic desde Preferencias. No son
    # QAction (no se registran en App._build_menu). El botón izquierdo no se
    # admite: es el que dibuja. Aplica igual a botones de mouse y a
    # los botones laterales de una tableta (ambos llegan como Qt.MouseButton
    # estándar — ver ui/input/tablet.py).
    "mouse_erase":       ("Ratón/tableta: borrar",              "Mouse:RightButton", "", "Ratón y tableta"),
    "mouse_pick_color":  ("Ratón/tableta: recoger color",       "", "", "Ratón y tableta"),
    "mouse_pan":         ("Ratón: desplazar lienzo (mantener)", "Mouse:MiddleButton", "", "Ratón y tableta"),
}


class ShortcutManager:
    """Mantiene la asignación action_id → (tecla_primaria, tecla_secundaria), con persistencia JSON."""

    def __init__(self):
        self._keys: dict[str, list[str]] = {k: [v[1], v[2]] for k, v in ACTIONS.items()}
        self._load()

    # ── Consulta / modificación ────────────────────────────────────────

    def keys(self, action_id: str) -> tuple[str, str]:
        """Devuelve (tecla_primaria, tecla_secundaria); "" si no está asignada."""
        k = self._keys.get(action_id)
        if k is None:
            defaults = ACTIONS.get(action_id, ("", "", "", ""))
            return (defaults[1], defaults[2])
        return (k[0], k[1])

    def key(self, action_id: str, index: int = 0) -> str:
        return self.keys(action_id)[index]

    def label(self, action_id: str) -> str:
        return ACTIONS.get(action_id, (action_id, "", "", ""))[0]

    def category(self, action_id: str) -> str:
        return ACTIONS.get(action_id, ("", "", "", ""))[3]

    def set_key(self, action_id: str, key_str: str, index: int = 0):
        self._keys.setdefault(action_id, ["", ""])[index] = key_str

    def reset(self, action_id: str):
        defaults = ACTIONS[action_id]
        self._keys[action_id] = [defaults[1], defaults[2]]

    def reset_all(self):
        for k, v in ACTIONS.items():
            self._keys[k] = [v[1], v[2]]

    # ── Persistencia ──────────────────────────────────────────────────

    def _load(self):
        if not _SC_FILE.exists():
            return
        try:
            with open(_SC_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in self._keys:
                    self._keys[k] = [v[0], v[1]]
        except Exception:
            pass

    def save(self):
        _CFG_DIR.mkdir(parents=True, exist_ok=True)
        overrides = {}
        for k, v in self._keys.items():
            defaults = ACTIONS.get(k, ("", "", "", ""))
            if (v[0], v[1]) != (defaults[1], defaults[2]):
                overrides[k] = v
        with open(_SC_FILE, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
