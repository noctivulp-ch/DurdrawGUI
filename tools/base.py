STANDBY   = "standby"
DRAWING   = "drawing"
SCROLLING = "scrolling"


def bresenham(x0, y0, x1, y1):
    """Genera las celdas del segmento (x0,y0)→(x1,y1) por el algoritmo de Bresenham."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy

_ALT_MASK   = 0x0008
_CTRL_MASK  = 0x0004


class ToolState:
    """Máquina de estados del canvas con soporte de quicktools."""

    def __init__(self, canvas_widget):
        self._canvas  = canvas_widget
        self._state   = STANDBY
        self._scroll_origin    = None
        self._scroll_view_orig = None
        self._space_held = False
        self._saved_tool = None   # herramienta previa al quicktool

    # ── Quicktool de teclado ──────────────────────────────────────────────

    def key_press(self, event):
        if event.keysym == "space" and self._state == STANDBY:
            self._space_held = True
            self._canvas.config(cursor="fleur")

    def key_release(self, event):
        if event.keysym == "space":
            self._space_held = False
            self._canvas.config(cursor="none")

    # ── Eventos de ratón ──────────────────────────────────────────────────

    def mouse_down(self, event, button):
        if self._state != STANDBY:
            return

        alt_held = bool(event.state & _ALT_MASK)

        if self._space_held or button == 2:
            self._state = SCROLLING
            self._scroll_origin    = (event.x, event.y)
            self._scroll_view_orig = (self._canvas.view_col, self._canvas.view_row)
            return

        if alt_held:
            # Quicktool: eyedropper temporal
            self._saved_tool = self._canvas.app.active_tool
            self._canvas.app.active_tool = self._canvas.app._tools["eyedropper"]

        self._state = DRAWING
        self._canvas.tool_start(event, button)

    def mouse_move(self, event):
        if self._state == DRAWING:
            self._canvas.tool_drag(event)
        elif self._state == SCROLLING:
            dx = (event.x - self._scroll_origin[0]) // self._canvas.cell_w
            dy = (event.y - self._scroll_origin[1]) // self._canvas.cell_h
            self._canvas.set_view(
                self._scroll_view_orig[0] - dx,
                self._scroll_view_orig[1] - dy,
            )
        else:
            self._canvas.update_cursor(event)

    def mouse_up(self, event, button):
        if self._state == DRAWING:
            self._canvas.tool_end(event, button)
            # Restaurar quicktool si había uno
            if self._saved_tool is not None:
                self._canvas.app.active_tool = self._saved_tool
                self._saved_tool = None
        self._state = STANDBY

    def mouse_leave(self, event):
        self._canvas.clear_cursor_highlight()
        self._canvas._canvas.config(cursor="none")

    def mouse_wheel(self, event):
        """Rueda del ratón: zoom si Ctrl, scroll vertical si no."""
        if event.state & _CTRL_MASK:
            if event.delta > 0 or event.num == 4:
                self._canvas.app.zoom_in(event.x, event.y)
            else:
                self._canvas.app.zoom_out(event.x, event.y)
        else:
            delta = -3 if (event.delta > 0 or event.num == 4) else 3
            self._canvas.set_view(
                self._canvas.view_col,
                self._canvas.view_row + delta,
            )
