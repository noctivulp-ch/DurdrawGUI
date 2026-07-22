import core.log as log
from core.brush import BrushContext
from core.tool_registry import register
from tools.base import bresenham

_log = log.get("tools")


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
        self._prev_cell  = None
        self._undo_cells = {}

    def on_start(self, col, row, button):
        self._undo_cells = {}
        self._prev_cell  = None
        self._button     = button
        _log.debug(f"pencil.start  ({col},{row})  btn={button}")
        self._paint(col, row, button)

    def on_drag(self, col, row):
        if (col, row) == self._prev_cell:
            return
        pc, pr = self._prev_cell
        for c, r in list(bresenham(pc, pr, col, row))[1:]:
            self._paint(c, r, self._button)

    def on_end(self, col, row, button):
        _log.debug(f"pencil.end  ({col},{row})  cells_modified={len(self._undo_cells)}")
        self._push_undo()
        self._prev_cell = None

    def _paint(self, col, row, button):
        frame = self.app.current_frame()
        brush = self.app.active_brush
        ctx = BrushContext(frame, col, row, self.app.fg_char, self.app.fg_color, self.app.bg_color)
        try:
            cells = brush.paint(ctx)
        except Exception as exc:
            _log.warning(f"pincel '{brush.name}' falló en paint(): {exc}")
            cells = []
        for dr, dc, ch, fg, bg in cells:
            r, c = row + dr, col + dc
            if 0 <= c < frame.width and 0 <= r < frame.height:
                ch = ch if ch is not None else self.app.fg_char
                fg = fg if fg is not None else self.app.fg_color
                bg = bg if bg is not None else self.app.bg_color
                if (r, c) not in self._undo_cells:
                    self._undo_cells[(r, c)] = (
                        frame.content[r][c],
                        frame.newColorMap[r][c][0],
                        frame.newColorMap[r][c][1],
                    )
                frame.content[r][c]     = ch
                frame.newColorMap[r][c] = [fg, bg]
                self.app.canvas_widget.update_cell(c, r, ch, fg, bg)
        self._prev_cell = (col, row)

    def _push_undo(self):
        frame      = self.app.current_frame()
        undo_cells = self._undo_cells
        redo_cells = {
            (r, c): (frame.content[r][c],
                     frame.newColorMap[r][c][0],
                     frame.newColorMap[r][c][1])
            for (r, c) in undo_cells
        }

        def undo():
            for (r, c), (ch, fg, bg) in undo_cells.items():
                frame.content[r][c]     = ch
                frame.newColorMap[r][c] = [fg, bg]
            self.app.canvas_widget.render_frame()

        def redo():
            for (r, c), (ch, fg, bg) in redo_cells.items():
                frame.content[r][c]     = ch
                frame.newColorMap[r][c] = [fg, bg]
            self.app.canvas_widget.render_frame()

        self.app.history.push(undo, redo)
        self._undo_cells = {}
