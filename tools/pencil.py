from copy import deepcopy
from core.tool_registry import register
from tools.base import bresenham


@register
class PencilTool:
    name = "pencil"
    icon = "✏"
    label = "Lápiz (B)"
    shortcut = "b"
    order = 0
    separator_before = False
    context_key = "brush"

    def __init__(self, app):
        self.app = app
        self._prev_cell = None
        self._snapshot  = None   # estado del frame antes del trazo

    def on_start(self, col, row, button):
        frame = self.app.current_frame()
        self._snapshot = (
            deepcopy(frame.content),
            deepcopy(frame.newColorMap),
        )
        self._prev_cell = None
        self._button = button
        self._paint(col, row, button)

    def on_drag(self, col, row):
        if (col, row) == self._prev_cell:
            return
        # Interpolar desde la celda anterior para no perder trazo en movimientos rápidos
        pc, pr = self._prev_cell
        for c, r in list(bresenham(pc, pr, col, row))[1:]:
            self._paint(c, r, self._button)

    def on_end(self, col, row, button):
        self._push_undo()
        self._prev_cell = None

    def _paint(self, col, row, button):
        frame = self.app.current_frame()
        ch = self.app.fg_char
        if button == 3:
            fg, bg = self.app.bg_color, self.app.fg_color
        else:
            fg, bg = self.app.fg_color, self.app.bg_color
        brush = self.app.active_brush
        for dr, dc in brush.cells:
            r, c = row + dr, col + dc
            if 0 <= c < frame.width and 0 <= r < frame.height:
                frame.content[r][c]     = ch
                frame.newColorMap[r][c] = [fg, bg]
                self.app.canvas_widget.update_cell(c, r, ch, fg, bg)
        self._prev_cell = (col, row)

    def _push_undo(self):
        snap_content, snap_colors = self._snapshot
        frame = self.app.current_frame()
        new_content = deepcopy(frame.content)
        new_colors  = deepcopy(frame.newColorMap)

        def undo():
            frame.content     = deepcopy(snap_content)
            frame.newColorMap = deepcopy(snap_colors)
            self.app.canvas_widget.render_frame(frame)

        def redo():
            frame.content     = deepcopy(new_content)
            frame.newColorMap = deepcopy(new_colors)
            self.app.canvas_widget.render_frame(frame)

        self.app.history.push(undo, redo)
