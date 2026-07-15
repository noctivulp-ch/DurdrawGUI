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
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            return
        ch, fg, bg = self.app.fg_char, self.app.fg_color, self.app.bg_color
        frame.content[row][col]      = ch
        frame.newColorMap[row][col]  = [fg, bg]
        self.app.canvas_widget.update_cell(col, row, ch, fg, bg)
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
