from core.tool_registry import register


@register
class EyedropperTool:
    name = "eyedropper"
    icon = "💧"
    label = "Cuentagotas (I)"
    shortcut = "i"
    order = 2
    separator_before = False
    context_key = "eyedropper"

    def __init__(self, app):
        self.app = app

    def on_start(self, col, row, button):
        frame = self.app.current_frame()
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            return
        ch     = frame.content[row][col]
        fg, bg = frame.newColorMap[row][col]
        self.app.set_active_colors(ch, fg, bg)

    def on_drag(self, col, row):
        self.on_start(col, row, 1)

    def on_end(self, col, row, button):
        pass
