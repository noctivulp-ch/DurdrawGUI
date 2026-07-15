from copy import deepcopy


class LineTool:
    name = "line"

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
        cells = list(_bresenham(c0, r0, col, row))
        ch = self.app.fg_char
        self.app.canvas_widget.draw_preview([(c, r, ch) for c, r in cells])

    def on_end(self, col, row, button):
        if self._start is None:
            return
        self.app.canvas_widget.clear_preview()
        c0, r0 = self._start
        cells = list(_bresenham(c0, r0, col, row))
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


def _bresenham(x0, y0, x1, y1):
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
