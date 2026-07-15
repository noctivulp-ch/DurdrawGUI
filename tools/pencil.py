from copy import deepcopy


class PencilTool:
    name = "pencil"

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
        self._paint(col, row, button)

    def on_drag(self, col, row):
        if (col, row) == self._prev_cell:
            return
        self._paint(col, row, 1)

    def on_end(self, col, row, button):
        self._push_undo()
        self._prev_cell = None

    def _paint(self, col, row, button):
        frame = self.app.current_frame()
        ch, fg, bg = self.app.fg_char, self.app.fg_color, self.app.bg_color
        size = getattr(self.app, 'context_bar', None)
        size = size.brush_size if size else 1
        half = size // 2
        for dr in range(-half, size - half):
            for dc in range(-half, size - half):
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
