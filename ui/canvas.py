import tkinter as tk
import tkinter.font
from tools.base import ToolState


def _build_palette_256():
    base = [
        "#000000", "#AA0000", "#00AA00", "#AA5500",
        "#0000AA", "#AA00AA", "#00AAAA", "#AAAAAA",
        "#555555", "#FF5555", "#55FF55", "#FFFF55",
        "#5555FF", "#FF55FF", "#55FFFF", "#FFFFFF",
    ]
    levels = [0, 95, 135, 175, 215, 255]
    cube = [f"#{r:02X}{g:02X}{b:02X}" for r in levels for g in levels for b in levels]
    grays = [f"#{v:02X}{v:02X}{v:02X}" for v in range(8, 248, 10)]
    return base + cube + grays


PALETTE_256 = _build_palette_256()
ANSI_COLORS = PALETTE_256[:16]   # alias backward-compat

_BASE_FONT_SIZE = 14
_ZOOM_STEPS = [6, 8, 10, 12, 14, 16, 18, 20, 24]


class AsciiCanvas(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app

        self._zoom_idx = _ZOOM_STEPS.index(_BASE_FONT_SIZE)
        self._font     = None
        self.cell_w    = 0
        self.cell_h    = 0
        self.view_col  = 0
        self.view_row  = 0
        self._cursor_cell = None
        self._sel_rect    = None   # (c0,r0,c1,r1) selección activa

        self._canvas = tk.Canvas(self, bg="#000000", cursor="none",
                                 highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        # Items de canvas
        self._items      = {}   # (col,row) → (rect_id, text_id)
        self._cursor_box = None
        self._sel_box    = None
        self._paste_box  = None

        self._state = ToolState(self)
        self._apply_zoom()
        self._bind_events()

    # ── Zoom ──────────────────────────────────────────────────────────────

    def _apply_zoom(self):
        size = _ZOOM_STEPS[self._zoom_idx]
        self._font  = tk.font.Font(family="Monospace", size=size)
        self.cell_w = self._font.measure("X")
        self.cell_h = self._font.metrics("linespace")
        pct = int(size / _BASE_FONT_SIZE * 100)
        if hasattr(self, 'app') and self.app:
            if hasattr(self.app, 'context_bar'):
                self.app.context_bar.set_zoom(pct)
        return pct

    def zoom_in(self):
        if self._zoom_idx < len(_ZOOM_STEPS) - 1:
            self._zoom_idx += 1
            self._apply_zoom()
            self.render_frame(self.app.current_frame())
        return int(_ZOOM_STEPS[self._zoom_idx] / _BASE_FONT_SIZE * 100)

    def zoom_out(self):
        if self._zoom_idx > 0:
            self._zoom_idx -= 1
            self._apply_zoom()
            self.render_frame(self.app.current_frame())
        return int(_ZOOM_STEPS[self._zoom_idx] / _BASE_FONT_SIZE * 100)

    def zoom_reset(self):
        self._zoom_idx = _ZOOM_STEPS.index(_BASE_FONT_SIZE)
        self._apply_zoom()
        self.render_frame(self.app.current_frame())
        return 100

    # ── Bindings ──────────────────────────────────────────────────────────

    def _bind_events(self):
        c = self._canvas
        # ButtonPress-1 incluye focus_set en un solo bind para evitar doble mouse_down
        c.bind("<ButtonPress-1>",   lambda e: (c.focus_set(), self._state.mouse_down(e, 1)))
        c.bind("<ButtonPress-2>",   lambda e: self._state.mouse_down(e, 2))
        c.bind("<ButtonPress-3>",   lambda e: self._state.mouse_down(e, 3))
        c.bind("<B1-Motion>",       lambda e: self._state.mouse_move(e))
        c.bind("<B2-Motion>",       lambda e: self._state.mouse_move(e))
        c.bind("<B3-Motion>",       lambda e: self._state.mouse_move(e))
        c.bind("<Motion>",          lambda e: self._state.mouse_move(e))
        c.bind("<ButtonRelease-1>", lambda e: self._state.mouse_up(e, 1))
        c.bind("<ButtonRelease-2>", lambda e: self._state.mouse_up(e, 2))
        c.bind("<ButtonRelease-3>", lambda e: self._state.mouse_up(e, 3))
        c.bind("<Leave>",           lambda e: self._state.mouse_leave(e))
        c.bind("<MouseWheel>",      lambda e: self._state.mouse_wheel(e))
        c.bind("<Button-4>",        lambda e: self._state.mouse_wheel(e))
        c.bind("<Button-5>",        lambda e: self._state.mouse_wheel(e))
        c.bind("<KeyPress>",        lambda e: self._state.key_press(e))
        c.bind("<KeyRelease>",      lambda e: self._state.key_release(e))

    # ── Coordenadas ───────────────────────────────────────────────────────

    def screen_to_cell(self, sx, sy):
        return sx // self.cell_w + self.view_col, sy // self.cell_h + self.view_row

    def cell_to_screen(self, col, row):
        return (col - self.view_col) * self.cell_w, (row - self.view_row) * self.cell_h

    # ── Renderizado ───────────────────────────────────────────────────────

    def draw_preview(self, cells):
        """Dibuja celdas de preview (rubber-band) sin tocar el modelo."""
        self._canvas.delete("preview")
        for col, row, ch in cells:
            x, y = self.cell_to_screen(col, row)
            self._canvas.create_text(
                x + self.cell_w // 2, y + self.cell_h // 2,
                text=ch, fill="#00FF88",
                font=self._font, anchor="center", tags="preview"
            )
        self._canvas.lift("overlay")

    def clear_preview(self):
        self._canvas.delete("preview")

    # ── Renderizado ───────────────────────────────────────────────────────

    def render_frame(self, frame):
        self._canvas.delete("cell")
        self._canvas.delete("grid")
        self._canvas.delete("preview")
        self._items.clear()
        self._cursor_box = self._canvas.create_rectangle(
            0, 0, 0, 0, outline="#FFFFFF", width=1, state="hidden", tags="overlay"
        )
        self._sel_box = self._canvas.create_rectangle(
            0, 0, 0, 0, outline="#FFFF00", width=1,
            dash=(4, 3), state="hidden", tags="overlay"
        )
        self._paste_box = self._canvas.create_rectangle(
            0, 0, 0, 0, outline="#00FF88", width=1,
            dash=(4, 3), state="hidden", tags="overlay"
        )
        for row in range(frame.height):
            for col in range(frame.width):
                self._draw_cell(col, row,
                                frame.content[row][col],
                                *frame.newColorMap[row][col])
        if getattr(self.app, '_show_grid', False):
            self._draw_grid(frame)

    def update_cell(self, col, row, ch, fg, bg):
        if (col, row) in self._items:
            rid, tid = self._items[(col, row)]
            x, y = self.cell_to_screen(col, row)
            self._canvas.coords(rid, x, y, x + self.cell_w, y + self.cell_h)
            self._canvas.itemconfig(rid, fill=PALETTE_256[bg % 256])
            self._canvas.coords(tid, x + self.cell_w // 2, y + self.cell_h // 2)
            self._canvas.itemconfig(tid, text=ch, fill=PALETTE_256[fg % 256],
                                    font=self._font)
        else:
            self._draw_cell(col, row, ch, fg, bg)
        self._canvas.lift("overlay")

    def _draw_cell(self, col, row, ch, fg, bg):
        x, y = self.cell_to_screen(col, row)
        rid = self._canvas.create_rectangle(
            x, y, x + self.cell_w, y + self.cell_h,
            fill=PALETTE_256[bg % 256], outline="", tags="cell"
        )
        tid = self._canvas.create_text(
            x + self.cell_w // 2, y + self.cell_h // 2,
            text=ch, fill=PALETTE_256[fg % 256],
            font=self._font, anchor="center", tags="cell"
        )
        self._items[(col, row)] = (rid, tid)

    def _draw_grid(self, frame):
        w = frame.width  * self.cell_w
        h = frame.height * self.cell_h
        for col in range(frame.width + 1):
            x = col * self.cell_w
            self._canvas.create_line(x, 0, x, h, fill="#2a2a2a", tags="grid")
        for row in range(frame.height + 1):
            y = row * self.cell_h
            self._canvas.create_line(0, y, w, y, fill="#2a2a2a", tags="grid")
        self._canvas.lift("overlay")

    # ── Scroll / vista ────────────────────────────────────────────────────

    def set_view(self, col, row):
        frame = self.app.current_frame()
        self.view_col = max(0, min(col, max(0, frame.width  - 1)))
        self.view_row = max(0, min(row, max(0, frame.height - 1)))
        self.render_frame(frame)

    # ── Cursor ────────────────────────────────────────────────────────────

    def update_cursor(self, event):
        col, row = self.screen_to_cell(event.x, event.y)
        frame = self.app.current_frame()
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            self.clear_cursor_highlight()
            self.app.statusbar.set_pos(None, None)
            return
        self._cursor_cell = (col, row)
        x, y = self.cell_to_screen(col, row)
        if self._cursor_box:
            self._canvas.coords(self._cursor_box, x, y,
                                x + self.cell_w, y + self.cell_h)
            self._canvas.itemconfig(self._cursor_box, state="normal")
        ch     = frame.content[row][col]
        fg, bg = frame.newColorMap[row][col]
        self.app.statusbar.set_pos(col, row, ch, fg, bg)
        # Mostrar preview del paste si hay clipboard
        if self.app.clipboard is not None and self.app.active_tool.name == "selection":
            self._update_paste_preview(col, row)

    def clear_cursor_highlight(self):
        self._cursor_cell = None
        if self._cursor_box:
            self._canvas.itemconfig(self._cursor_box, state="hidden")

    # ── Selección visual ──────────────────────────────────────────────────

    def set_selection(self, c0, r0, c1, r1):
        self._sel_rect = (c0, r0, c1, r1)
        if not self._sel_box:
            return
        x0, y0 = self.cell_to_screen(c0, r0)
        x1, y1 = self.cell_to_screen(c1 + 1, r1 + 1)
        self._canvas.coords(self._sel_box, x0, y0, x1, y1)
        self._canvas.itemconfig(self._sel_box, state="normal")

    def clear_selection(self):
        self._sel_rect = None
        if self._sel_box:
            self._canvas.itemconfig(self._sel_box, state="hidden")
        if self._paste_box:
            self._canvas.itemconfig(self._paste_box, state="hidden")

    def _update_paste_preview(self, col, row):
        if not self.app.clipboard or not self._paste_box:
            return
        rows = len(self.app.clipboard)
        cols = len(self.app.clipboard[0]) if rows else 0
        x0, y0 = self.cell_to_screen(col, row)
        x1, y1 = self.cell_to_screen(col + cols, row + rows)
        self._canvas.coords(self._paste_box, x0, y0, x1, y1)
        self._canvas.itemconfig(self._paste_box, state="normal")

    # ── Tool callbacks ────────────────────────────────────────────────────

    def tool_start(self, event, button):
        col, row = self.screen_to_cell(event.x, event.y)
        self.app.active_tool.on_start(col, row, button)

    def tool_drag(self, event):
        col, row = self.screen_to_cell(event.x, event.y)
        self.update_cursor(event)
        self.app.active_tool.on_drag(col, row)

    def tool_end(self, event, button):
        col, row = self.screen_to_cell(event.x, event.y)
        self.app.active_tool.on_end(col, row, button)
