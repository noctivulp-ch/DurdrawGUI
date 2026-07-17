from copy import deepcopy
import core.log as log
from core.tool_registry import register
from tools.base import bresenham

_log = log.get("tools")


@register
class EraserTool:
    name = "eraser"
    icon = "⬜"
    label = "Borrador (E)"
    shortcut = "e"
    order = 1
    separator_before = False
    context_key = "brush"

    def __init__(self, app):
        self.app = app
        self._prev_cell = None
        self._snapshot  = None

    def on_start(self, col, row, button):
        frame = self.app.current_frame()
        self._snapshot = (
            deepcopy(frame.content),
            deepcopy(frame.newColorMap),
        )
        self._prev_cell = None
        self._button = button
        _log.debug(f"eraser.start  ({col},{row})  btn={button}")
        self._erase(col, row, button)

    def on_drag(self, col, row):
        if (col, row) == self._prev_cell:
            return
        pc, pr = self._prev_cell
        for c, r in list(bresenham(pc, pr, col, row))[1:]:
            self._erase(c, r, self._button)

    def on_end(self, col, row, button):
        _log.debug(f"eraser.end  ({col},{row})")
        self._push_undo()
        self._prev_cell = None

    def _erase(self, col, row, button=1):
        frame = self.app.current_frame()
        if button == 3:
            ch, fg, bg = self.app.fg_char, self.app.fg_color, self.app.bg_color
        else:
            ch, fg, bg = " ", 7, 0
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
