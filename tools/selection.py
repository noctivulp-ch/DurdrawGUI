from copy import deepcopy


class SelectionTool:
    name = "selection"

    def __init__(self, app):
        self.app = app
        self._start = None
        self._end   = None

    def on_start(self, col, row, button):
        self._start = (col, row)
        self._end   = (col, row)
        self.app.canvas_widget.set_selection(col, row, col, row)

    def on_drag(self, col, row):
        self._end = (col, row)
        c0, r0 = self._start
        self.app.canvas_widget.set_selection(
            min(c0, col), min(r0, row),
            max(c0, col), max(r0, row),
        )

    def on_end(self, col, row, button):
        c0, r0 = self._start
        c1, r1 = max(c0, col), max(r0, row)
        c0, r0 = min(c0, col), min(r0, row)
        self.app.set_selection_rect(c0, r0, c1, r1)

    def deselect(self):
        self._start = self._end = None
        self.app.canvas_widget.clear_selection()
        self.app.set_selection_rect(None, None, None, None)
