"""Driver de teclado — atajos sueltos (Space/Ctrl), la tecla de "recoger
color" en modo ratón, y todo el modo cursor de teclado (dibujo sin ratón).

El estado que paintEvent() necesita (cursor de teclado, fila de color/carácter
activa, guías de cel) sigue viviendo en AsciiCanvas — ver ui/input/__init__.py.
"""

from PySide6.QtCore import Qt, QRect, QKeyCombination
from PySide6.QtGui  import QKeySequence

import core.log as log
from ui.input.base import InputDriver

_log_input = log.get("input")


class KeyboardInput(InputDriver):
    def toggle_draw_mode(self):
        """Prende/apaga el modo cursor de teclado. Se llama desde el QAction
        global (Ctrl+Tab) — como funciona sin importar qué widget tenga el
        foco, hay que dárselo al canvas explícitamente al activar, si no las
        teclas del modo siguen yendo al widget que tuviera el foco antes."""
        canvas = self.canvas
        turning_on = not self.app._kb_draw_mode
        _log_input.debug(f"kb_draw_toggle  → {'ON' if turning_on else 'OFF'}")
        self.app.set_kb_draw_mode(turning_on)
        if turning_on:
            canvas.setFocus()
            self._clamp_kb_cursor()
            self.app.char_panel.set_kb_row_indicator(canvas._kb_char_row)
        else:
            self.app.char_panel.set_kb_row_indicator(None)
        canvas.update()

    def press(self, event):
        canvas = self.canvas

        if self._matches_action("kb_draw_toggle", event):
            self.toggle_draw_mode()
            return

        if self.app._kb_draw_mode:
            if event.key() == Qt.Key.Key_Escape:
                _log_input.debug("kb_draw  Escape → OFF")
                self.app.set_kb_draw_mode(False)
                self.app.char_panel.set_kb_row_indicator(None)
                canvas.update()
                return
            if self._handle_kb_draw_key(event):
                return
            event.ignore()
            return

        if event.key() == Qt.Key.Key_Space:
            canvas.mouse_input.space_press()
        elif event.key() in (Qt.Key.Key_Control,):
            canvas._ctrl_held       = True
            canvas._cel_bounds_a    = None   # recomputa para la capa activa actual
            canvas._cel_guides_key  = None
            canvas._cel_guides_data = None
            _log_input.debug(f"key_press  Ctrl → cel guides  cursor={canvas._cursor_cell}")
            if canvas._cursor_cell:
                col, row = canvas._cursor_cell
                canvas._cel_guides_pos = (col, row)
                canvas._update_cel_guides(self.app.doc, col, row, QRect())
        elif self._matches_action("kb_pick_color", event):
            canvas.mouse_input.set_picker_held(True)
            _log_input.debug("key_press  pick_color-hold ON (modo ratón)")
        else:
            event.ignore()  # propagar al padre (atajos de app)

    def release(self, event):
        canvas = self.canvas
        if event.key() == Qt.Key.Key_Space:
            canvas.mouse_input.space_release()
        elif event.key() in (Qt.Key.Key_Control,):
            canvas._ctrl_held       = False
            canvas._cel_guides_pos  = None
            canvas._cel_guides_data = None
            canvas._cel_guides_key  = None
            _log_input.debug("key_release  Ctrl → cel guides off")
            canvas.update()
        elif self._matches_action("kb_pick_color", event):
            canvas.mouse_input.set_picker_held(False)
            _log_input.debug("key_release  pick_color-hold OFF (modo ratón)")
        else:
            event.ignore()

    # ── Modo cursor de teclado (dibujo sin ratón) ───────────────────────────

    def _matches_action(self, action_id: str, event) -> bool:
        combo = QKeyCombination(event.modifiers(), Qt.Key(event.key()))
        text  = QKeySequence(combo).toString(QKeySequence.SequenceFormat.PortableText)
        return bool(text) and text in self.app.shortcut_mgr.keys(action_id)

    def _handle_kb_draw_key(self, event) -> bool:
        """Interpreta una tecla mientras el modo cursor está activo.
        Devuelve True si la consumió (no debe propagarse)."""
        canvas = self.canvas
        doc = self.app.doc
        if canvas._kb_cursor is None:
            self._clamp_kb_cursor()
        col, row = canvas._kb_cursor
        _log_input.debug(f"kb_draw  key={event.text()!r}  cursor=({col},{row})  target={canvas._kb_target}")

        if self._matches_action("kb_cursor_up", event):
            row = max(0, row - 1)
        elif self._matches_action("kb_cursor_down", event):
            row = min(doc.height - 1, row + 1)
        elif self._matches_action("kb_cursor_left", event):
            col = max(0, col - 1)
        elif self._matches_action("kb_cursor_right", event):
            col = min(doc.width - 1, col + 1)
        elif self._matches_action("kb_pan_up", event):
            canvas.set_view(canvas._view_col, canvas._view_row - 1)
            return True
        elif self._matches_action("kb_pan_down", event):
            canvas.set_view(canvas._view_col, canvas._view_row + 1)
            return True
        elif self._matches_action("kb_pan_left", event):
            canvas.set_view(canvas._view_col - 1, canvas._view_row)
            return True
        elif self._matches_action("kb_pan_right", event):
            canvas.set_view(canvas._view_col + 1, canvas._view_row)
            return True
        elif self._matches_action("kb_execute", event):
            _log_input.debug(f"kb_draw  execute tool={self.app.active_tool.name}  ({col},{row})")
            self._kb_run_tool(col, row)
            return True
        elif self._matches_action("kb_erase", event):
            _log_input.debug(f"kb_draw  erase  ({col},{row})")
            self._erase_at(col, row)
            return True
        elif self._matches_action("kb_toggle_fgbg", event):
            canvas._kb_target = "bg" if canvas._kb_target == "fg" else "fg"
            _log_input.debug(f"kb_draw  toggle_fgbg  → {canvas._kb_target}")
            self.app.statusbar.showMessage(
                f"Editando color de {'fondo' if canvas._kb_target == 'bg' else 'frente'}", 1500)
            canvas.update()
            return True
        elif self._matches_action("kb_pick_color", event):
            _log_input.debug(f"kb_draw  pick_color  ({col},{row})")
            self.app._tools["eyedropper"].on_start(col, row, 1)
            return True
        elif self._matches_action("kb_color_up", event):
            self._kb_cycle_color(-1, axis="row")
            return True
        elif self._matches_action("kb_color_down", event):
            self._kb_cycle_color(+1, axis="row")
            return True
        elif self._matches_action("kb_color_left", event):
            self._kb_cycle_color(-1, axis="col")
            return True
        elif self._matches_action("kb_color_right", event):
            self._kb_cycle_color(+1, axis="col")
            return True
        elif self._matches_action("kb_char_row_up", event):
            canvas._kb_char_row = max(0, canvas._kb_char_row - 1)
            self.app.char_panel.set_kb_row_indicator(canvas._kb_char_row)
            _log_input.debug(f"kb_draw  char_row → {canvas._kb_char_row}")
            canvas.update()
            return True
        elif self._matches_action("kb_char_row_down", event):
            panel   = self.app.char_panel
            n_chars = len(panel.group_chars(panel.current_group_index()))
            max_row = max(0, (n_chars - 1) // 10)
            canvas._kb_char_row = min(max_row, canvas._kb_char_row + 1)
            panel.set_kb_row_indicator(canvas._kb_char_row)
            _log_input.debug(f"kb_draw  char_row → {canvas._kb_char_row}")
            canvas.update()
            return True
        elif self._matches_action("kb_char_group_prev", event):
            panel = self.app.char_panel
            n     = len(panel.group_names())
            panel.select_group((panel.current_group_index() - 1) % n)
            canvas._kb_char_row = 0
            panel.set_kb_row_indicator(canvas._kb_char_row)
            _log_input.debug(f"kb_draw  char_group → {panel.current_group_index()}")
            canvas.update()
            return True
        elif self._matches_action("kb_char_group_next", event):
            panel = self.app.char_panel
            n     = len(panel.group_names())
            panel.select_group((panel.current_group_index() + 1) % n)
            canvas._kb_char_row = 0
            panel.set_kb_row_indicator(canvas._kb_char_row)
            _log_input.debug(f"kb_draw  char_group → {panel.current_group_index()}")
            canvas.update()
            return True
        elif (Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9
              and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            slot = 9 if event.key() == Qt.Key.Key_0 else event.key() - Qt.Key.Key_1
            ok   = self.app.char_panel.pick_slot(canvas._kb_char_row, slot)
            _log_input.debug(f"kb_draw  pick_char  row={canvas._kb_char_row}  slot={slot}  ok={ok}")
            return True
        else:
            _log_input.debug(f"kb_draw  key sin acción asignada: {event.text()!r}")
            return False

        canvas._kb_cursor = (col, row)
        self._ensure_kb_cursor_visible()
        canvas.update()
        return True

    def _clamp_kb_cursor(self):
        """Ancla/reancla el cursor de teclado dentro de los límites del documento.
        _view_col/_view_row pueden ser negativos (lienzo centrado si es más
        chico que el viewport), así que no sirven como posición sin recortar."""
        canvas = self.canvas
        doc = self.app.doc
        col, row = canvas._kb_cursor if canvas._kb_cursor is not None else (canvas._view_col, canvas._view_row)
        col = max(0, min(int(col), doc.width  - 1))
        row = max(0, min(int(row), doc.height - 1))
        canvas._kb_cursor = (col, row)

    def _kb_run_tool(self, col: int, row: int):
        """Ejecuta la herramienta activa en una sola celda (equivale a clic sin arrastre)."""
        tool = self.app.active_tool
        tool.on_start(col, row, 1)
        tool.on_end(col, row, 1)
        if self.canvas.minimap:
            self.canvas.minimap.invalidate()
        self.canvas.update()

    def _erase_at(self, col: int, row: int):
        """Borra una celda con la herramienta borrador, sin cambiar la activa (como el clic derecho)."""
        saved = self.app.active_tool
        self.app.active_tool = self.app._tools["eraser"]
        self.app.active_tool.on_start(col, row, 1)
        self.app.active_tool.on_end(col, row, 1)
        self.app.active_tool = saved
        if self.canvas.minimap:
            self.canvas.minimap.invalidate()
        self.canvas.update()

    def _kb_cycle_color(self, direction: int, axis: str):
        """Navega la paleta activa; el color bajo el cursor se aplica de inmediato
        (fg o bg según _kb_target). axis='row' salta de fila (I/K), 'col' de
        columna (J/L) — misma grilla que ColorPanel."""
        from core.color_service import palette_cols
        canvas = self.canvas
        svc   = self.app.color_service
        count = svc.count()
        step  = palette_cols(svc.mode) if axis == "row" else 1
        current = self.app.fg_color if canvas._kb_target == "fg" else self.app.bg_color
        new_idx = (current + direction * step) % count
        _log_input.debug(f"kb_draw  color {canvas._kb_target}  {current} → {new_idx}  (axis={axis})")
        if canvas._kb_target == "fg":
            self.app.set_fg_color(new_idx)
        else:
            self.app.set_bg_color(new_idx)

    def _ensure_kb_cursor_visible(self):
        """Desplaza la vista lo mínimo necesario para mantener el cursor de teclado visible."""
        canvas = self.canvas
        col, row = canvas._kb_cursor
        vis_c = max(1, canvas.width()  // canvas._cell_w)
        vis_r = max(1, canvas.height() // canvas._cell_h)
        new_col, new_row = canvas._view_col, canvas._view_row
        if col < canvas._view_col:
            new_col = col
        elif col >= canvas._view_col + vis_c:
            new_col = col - vis_c + 1
        if row < canvas._view_row:
            new_row = row
        elif row >= canvas._view_row + vis_r:
            new_row = row - vis_r + 1
        if (new_col, new_row) != (canvas._view_col, canvas._view_row):
            canvas.set_view(new_col, new_row)
