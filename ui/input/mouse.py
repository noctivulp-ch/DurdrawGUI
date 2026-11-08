"""Driver de mouse — clic/arrastre/rueda. Mecánica de trazo (bresenham,
snapshots de undo) vive en tools/; acá solo se decide QUÉ herramienta recibe
el gesto y con qué coordenadas."""

from PySide6.QtCore import Qt

import core.log as log
from ui.input.base import InputDriver

_log_input = log.get("input")

STANDBY   = "standby"
DRAWING   = "drawing"
SCROLLING = "scrolling"


class MouseInput(InputDriver):
    def __init__(self, canvas, app):
        super().__init__(canvas, app)
        self.tool_state         = STANDBY
        self.space_held         = False
        self.picker_held        = False   # tecla kb_pick_color sostenida (modo ratón)
        self._scroll_origin     = None
        self._scroll_view_orig  = None
        self._saved_tool        = None

    # ── Puente con KeyboardInput (Space = pan sosteniendo; F = cuentagotas) ─

    def space_press(self):
        if self.tool_state == STANDBY:
            self.space_held = True
            self.canvas.setCursor(Qt.CursorShape.SizeAllCursor)
            _log_input.debug("key_press  Space → scroll mode")

    def space_release(self):
        self.space_held = False
        self.canvas.setCursor(Qt.CursorShape.BlankCursor)

    def set_picker_held(self, held: bool):
        self.picker_held = held

    # ── Eventos Qt ───────────────────────────────────────────────────────────

    def press(self, event):
        if self.tool_state != STANDBY:
            return
        x, y = int(event.position().x()), int(event.position().y())
        btn  = event.button()
        alt  = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)

        if self.space_held or self.matches_mouse_button("mouse_pan", btn):
            self.tool_state        = SCROLLING
            self._scroll_origin    = (x, y)
            self._scroll_view_orig = (int(self.canvas._view_col), int(self.canvas._view_row))
            _log_input.debug(f"mouse_press  scroll_start  ({x},{y})")
            return

        # mouse_erase/mouse_pick_color son configurables (Preferencias →
        # Ratón y tableta); alt o F sostenida (kb_pick_color) siguen andando
        # como atajos fijos además del binding. Se sustituye temporalmente
        # la herramienta activa — release() la restaura.
        if self.matches_mouse_button("mouse_erase", btn):
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = self.app._tools["eraser"]
        elif alt or self.picker_held or self.matches_mouse_button("mouse_pick_color", btn):
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = self.app._tools["eyedropper"]

        col, row = self.canvas.screen_to_cell(x, y)
        _log_input.debug(f"mouse_press  btn={btn.name}  ({x},{y}) → cell({col},{row})  tool={self.app.active_tool.name}")
        self.tool_state = DRAWING
        self.app.active_tool.on_start(col, row, 1)

    def move(self, event):
        x, y = int(event.position().x()), int(event.position().y())
        col, row = self.canvas.screen_to_cell(x, y)

        if self.tool_state == DRAWING:
            self.canvas.update_cursor(col, row)
            self.app.active_tool.on_drag(col, row)
        elif self.tool_state == SCROLLING:
            ox, oy = self._scroll_origin
            dx = (x - ox) // self.canvas._cell_w
            dy = (y - oy) // self.canvas._cell_h
            self.canvas.set_view(self._scroll_view_orig[0] - dx,
                                 self._scroll_view_orig[1] - dy)
            return  # SizeAllCursor ya está activo; no sobreescribir
        else:
            self.canvas.update_cursor(col, row)

        # Cursor del sistema: cruceta fuera del área del documento, invisible dentro
        # (el canvas dibuja su propio indicador de celda sobre el documento)
        if not self.space_held:
            doc   = self.app.doc
            shape = (Qt.CursorShape.BlankCursor
                     if 0 <= col < doc.width and 0 <= row < doc.height
                     else Qt.CursorShape.CrossCursor)
            if self.canvas.cursor().shape() != shape:
                self.canvas.setCursor(shape)

    def release(self, event):
        if self.tool_state == DRAWING:
            x, y     = int(event.position().x()), int(event.position().y())
            col, row = self.canvas.screen_to_cell(x, y)
            _log_input.debug(f"mouse_release  btn={event.button().name}  cell({col},{row})")
            self.app.active_tool.on_end(col, row, 1)
            if self.canvas.minimap:
                self.canvas.minimap.invalidate()
                self.canvas.update()   # repintado completo: el dirty de on_end puede excluir el minimap
            if self._saved_tool is not None:
                self.app.active_tool = self._saved_tool
                self._saved_tool     = None
        self.tool_state = STANDBY

    def wheel(self, event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.app.swap_colors()
            return
        ctrl  = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        dy = event.angleDelta().y()
        dx = event.angleDelta().x()   # rueda horizontal nativa (trackpad) o gesto lateral
        x, y = int(event.position().x()), int(event.position().y())
        if ctrl:
            if dy > 0:
                self.app.zoom_in(x, y)
            else:
                self.app.zoom_out(x, y)
        elif shift or dx:
            delta  = dx if dx else dy
            scroll = -3 if delta > 0 else 3
            self.canvas.set_view(self.canvas._view_col + scroll, self.canvas._view_row)
        else:
            scroll = -3 if dy > 0 else 3
            self.canvas.set_view(self.canvas._view_col, self.canvas._view_row + scroll)
