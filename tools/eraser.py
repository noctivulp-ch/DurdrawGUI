from copy import deepcopy


class EraserTool:
    name = "eraser"

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
        self._erase(col, row)

    def on_drag(self, col, row):
        if (col, row) == self._prev_cell:
            return
        self._erase(col, row)

    def on_end(self, col, row, button):
        self._push_undo()
        self._prev_cell = None

    def _erase(self, col, row):
        frame = self.app.current_frame()
        size = getattr(self.app, 'context_bar', None)
        size = size.brush_size if size else 1
        half = size // 2
        for dr in range(-half, size - half):
            for dc in range(-half, size - half):
                r, c = row + dr, col + dc
                if 0 <= c < frame.width and 0 <= r < frame.height:
                    frame.content[r][c]     = " "
                    frame.newColorMap[r][c] = [7, 0]
                    self.app.canvas_widget.update_cell(c, r, " ", 7, 0)
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
