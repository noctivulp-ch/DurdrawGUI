from copy import deepcopy
from collections import deque


class FillTool:
    name = "fill"

    def __init__(self, app):
        self.app = app
        self._snapshot = None

    def on_start(self, col, row, button):
        frame = self.app.current_frame()
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            return
        self._snapshot = (deepcopy(frame.content), deepcopy(frame.newColorMap))

        target_ch  = frame.content[row][col]
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

        for c, r in changed:
            self.app.canvas_widget.update_cell(c, r, new_ch, new_fg, new_bg)

        self._push_undo(frame)

    def on_drag(self, col, row):
        pass

    def on_end(self, col, row, button):
        pass

    def _push_undo(self, frame):
        snap_content, snap_colors = self._snapshot
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
