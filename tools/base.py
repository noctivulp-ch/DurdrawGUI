STANDBY  = "standby"
DRAWING  = "drawing"
SCROLLING = "scrolling"


class ToolState:
    """Máquina de estados del canvas. El estado activo maneja todos los eventos."""

    def __init__(self, canvas_widget):
        self._canvas = canvas_widget
        self._state = STANDBY
        self._scroll_origin = None   # (x, y) en pantalla al iniciar scroll
        self._scroll_view_origin = None

    # ── Transiciones ──────────────────────────────────────────────────────────

    def mouse_down(self, event, button):
        if self._state != STANDBY:
            return
        if button == 2 or (button == 1 and event.state & 0x0001):  # rueda o Shift
            self._state = SCROLLING
            self._scroll_origin = (event.x, event.y)
            self._scroll_view_origin = (self._canvas.view_col, self._canvas.view_row)
        else:
            self._state = DRAWING
            self._canvas.tool_start(event, button)

    def mouse_move(self, event):
        if self._state == DRAWING:
            self._canvas.tool_drag(event)
        elif self._state == SCROLLING:
            dx = (event.x - self._scroll_origin[0]) // self._canvas.cell_w
            dy = (event.y - self._scroll_origin[1]) // self._canvas.cell_h
            self._canvas.set_view(
                self._scroll_view_origin[0] - dx,
                self._scroll_view_origin[1] - dy,
            )
        else:
            self._canvas.update_cursor(event)

    def mouse_up(self, event, button):
        if self._state == DRAWING:
            self._canvas.tool_end(event, button)
        self._state = STANDBY

    def mouse_leave(self, event):
        self._canvas.clear_cursor_highlight()
