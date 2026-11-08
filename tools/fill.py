from collections import deque
import core.log as log
from core.tool_registry import register
from core.grid_copy import copy_content, copy_colors

_log = log.get("tools")


@register
class FillTool:
    name = "fill"
    icon = "🪣"
    label = "Relleno (G)"
    shortcut = "g"
    order = 3
    separator_before = False
    context_key = "fill"

    def __init__(self, app):
        self.app = app
        self._snapshot = None

    def on_start(self, col, row, button):
        frame = self.app.current_frame()
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            return
        self._snapshot = (copy_content(frame.content), copy_colors(frame.newColorMap))

        target_ch  = frame.content[row][col]
        _log.debug(f"fill.start  ({col},{row})  target='{target_ch}'")
        target_fg, target_bg = frame.newColorMap[row][col]
        new_ch  = self.app.fg_char
        new_fg  = self.app.fg_color
        new_bg  = self.app.bg_color

        # No hacer nada si ya tiene el mismo contenido
        if target_ch == new_ch and target_fg == new_fg and target_bg == new_bg:
            return

        visited = set()
        queue   = deque([(col, row)])
        changed = []
        while queue:
            c, r = queue.popleft()
            if (c, r) in visited:
                continue
            if not (0 <= c < frame.width and 0 <= r < frame.height):
                continue
            if frame.content[r][c] != target_ch:
                continue
            fg, bg = frame.newColorMap[r][c]
            if fg != target_fg or bg != target_bg:
                continue
            visited.add((c, r))
            frame.content[r][c]     = new_ch
            frame.newColorMap[r][c] = [new_fg, new_bg]
            changed.append((c, r))
            queue.extend([(c+1, r), (c-1, r), (c, r+1), (c, r-1)])

        self.app.canvas_widget.update_cells(changed)

        _log.debug(f"fill.end  cells_filled={len(changed)}")
        self._push_undo(frame)

    def on_drag(self, col, row):
        pass

    def on_end(self, col, row, button):
        pass

    def _push_undo(self, frame):
        snap_content, snap_colors = self._snapshot
        new_content = copy_content(frame.content)
        new_colors  = copy_colors(frame.newColorMap)

        def undo():
            frame.content     = copy_content(snap_content)
            frame.newColorMap = copy_colors(snap_colors)
            self.app.canvas_widget.render_frame(frame)

        def redo():
            frame.content     = copy_content(new_content)
            frame.newColorMap = copy_colors(new_colors)
            self.app.canvas_widget.render_frame(frame)

        self.app.history.push(undo, redo)
