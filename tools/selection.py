from copy import deepcopy
import core.log as log
from core.tool_registry import register

_log = log.get("tools")


@register
class SelectionTool:
    name = "selection"
    icon = "⬚"
    label = "Selección (S)"
    shortcut = "s"
    order = 4
    separator_before = False
    context_key = "selection"

    def __init__(self, app):
        self.app = app
        self._start = None
        self._end   = None

    def _clamp(self, col, row):
        doc = self.app.doc
        return (
            max(0, min(col, doc.width  - 1)),
            max(0, min(row, doc.height - 1)),
        )

    def on_start(self, col, row, button):
        col, row = self._clamp(col, row)
        self._start = (col, row)
        self._end   = (col, row)
        self.app.canvas_widget.set_selection(col, row, col, row)

    def on_drag(self, col, row):
        col, row = self._clamp(col, row)
        self._end = (col, row)
        c0, r0 = self._start
        self.app.canvas_widget.set_selection(
            min(c0, col), min(r0, row),
            max(c0, col), max(r0, row),
        )

    def on_end(self, col, row, button):
        col, row = self._clamp(col, row)
        c0, r0 = self._start
        c1, r1 = max(c0, col), max(r0, row)
        c0, r0 = min(c0, col), min(r0, row)
        self.app.set_selection_rect(c0, r0, c1, r1)

    def deselect(self):
        self._start = self._end = None
        self.app.canvas_widget.clear_selection()
        self.app.set_selection_rect(None, None, None, None)
