import math
from copy import deepcopy
import core.log as log
from core.tool_registry import register

_log = log.get("tools")


@register
class EllipseTool:
    name = "ellipse"
    icon = "◯"
    label = "Elipse (O)"
    shortcut = "o"
    order = 7
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
        cells = _ellipse_outline(c0, r0, col, row)
        ch = self.app.fg_char
        self.app.canvas_widget.draw_preview([(c, r, ch) for c, r in cells])

    def on_end(self, col, row, button):
        if self._start is None:
            return
        self.app.canvas_widget.clear_preview()
        c0, r0 = self._start
        filled = getattr(self.app.context_bar, 'shape_filled', False)
        cells = _ellipse_fill(c0, r0, col, row) if filled else _ellipse_outline(c0, r0, col, row)
        self._commit(cells, button)
        self._start = None

    def _commit(self, cells, button):
        frame = self.app.current_frame()
        ch = self.app.fg_char
        fg, bg = self.app.fg_color, self.app.bg_color
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


def _ellipse_outline(c0, r0, c1, r1):
    cx = (c0 + c1) / 2
    cy = (r0 + r1) / 2
    a = abs(c1 - c0) / 2
    b = abs(r1 - r0) / 2
    pts = set()
    if a == 0 and b == 0:
        pts.add((round(cx), round(cy)))
        return pts
    steps = max(int(2 * math.pi * max(a, b) * 2), 48)
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        # Corrección de aspecto: los chars son ~2x más altos que anchos
        c = round(cx + a * math.cos(t))
        r = round(cy + b * math.sin(t) * 0.5)
        pts.add((c, r))
    return pts


def _ellipse_fill(c0, r0, c1, r1):
    cx = (c0 + c1) / 2
    cy = (r0 + r1) / 2
    a = abs(c1 - c0) / 2
    b = abs(r1 - r0) / 2 * 0.5   # mismo factor de aspecto
    pts = set()
    if a == 0 or b == 0:
        for r in range(min(r0, r1), max(r0, r1) + 1):
            for c in range(min(c0, c1), max(c0, c1) + 1):
                pts.add((c, r))
        return pts
    for r in range(min(r0, r1), max(r0, r1) + 1):
        dy = r - cy
        if abs(dy) > b:
            continue
        dx = a * math.sqrt(max(0, 1 - (dy / b) ** 2))
        for c in range(round(cx - dx), round(cx + dx) + 1):
            pts.add((c, r))
    return pts
