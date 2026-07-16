from copy import deepcopy
from core.tool_registry import register


@register
class RectTool:
    name = "rect"
    icon = "▭"
    label = "Rectángulo (R)"
    shortcut = "r"
    order = 6
    separator_before = False
    context_key = "shape"

    def __init__(self, app):
        self.app = app
        self._start = None
        self._button = 1

    def on_start(self, col, row, button):
        self._start = (col, row)
        self._button = button

    def on_drag(self, col, row):
        if self._start is None:
            return
        c0, r0 = self._start
        cells = _rect_outline(c0, r0, col, row)
        ch = self.app.fg_char
        self.app.canvas_widget.draw_preview([(c, r, ch) for c, r in cells])

    def on_end(self, col, row, button):
        if self._start is None:
            return
        self.app.canvas_widget.clear_preview()
        c0, r0 = self._start
        filled = getattr(self.app.context_bar, 'shape_filled', False)
        cells = _rect_fill(c0, r0, col, row) if filled else _rect_outline(c0, r0, col, row)
        self._commit(cells, button)
        self._start = None

    def _commit(self, cells, button):
        frame = self.app.current_frame()
        ch = self.app.fg_char
        fg, bg = (self.app.bg_color, self.app.fg_color) if button == 3 else (self.app.fg_color, self.app.bg_color)
        snap_c = deepcopy(frame.content)
        snap_m = deepcopy(frame.newColorMap)
        for c, r in cells:
            if 0 <= c < frame.width and 0 <= r < frame.height:
                frame.content[r][c] = ch
                frame.newColorMap[r][c] = [fg, bg]
        self.app.canvas_widget.render_frame(frame)
        new_c = deepcopy(frame.content)
        new_m = deepcopy(frame.newColorMap)

        def undo():
            frame.content = deepcopy(snap_c)
            frame.newColorMap = deepcopy(snap_m)
            self.app.canvas_widget.render_frame(frame)

        def redo():
            frame.content = deepcopy(new_c)
            frame.newColorMap = deepcopy(new_m)
            self.app.canvas_widget.render_frame(frame)

        self.app.history.push(undo, redo)


def _rect_outline(c0, r0, c1, r1):
    x0, x1 = min(c0, c1), max(c0, c1)
    y0, y1 = min(r0, r1), max(r0, r1)
    pts = set()
    for c in range(x0, x1 + 1):
        pts.add((c, y0))
        pts.add((c, y1))
    for r in range(y0 + 1, y1):
        pts.add((x0, r))
        pts.add((x1, r))
    return pts


def _rect_fill(c0, r0, c1, r1):
    x0, x1 = min(c0, c1), max(c0, c1)
    y0, y1 = min(r0, r1), max(r0, r1)
    return [(c, r) for r in range(y0, y1 + 1) for c in range(x0, x1 + 1)]
