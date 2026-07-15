import tkinter as tk
from copy import deepcopy
from tools.base import ToolState

# Paleta ANSI 16 colores (índice durdraw → hex)
ANSI_COLORS = [
    "#000000",  # 0  negro
    "#AA0000",  # 1  rojo oscuro
    "#00AA00",  # 2  verde oscuro
    "#AA5500",  # 3  marrón/amarillo oscuro
    "#0000AA",  # 4  azul oscuro
    "#AA00AA",  # 5  magenta oscuro
    "#00AAAA",  # 6  cian oscuro
    "#AAAAAA",  # 7  gris claro
    "#555555",  # 8  gris oscuro (negro brillante)
    "#FF5555",  # 9  rojo brillante
    "#55FF55",  # 10 verde brillante
    "#FFFF55",  # 11 amarillo brillante
    "#5555FF",  # 12 azul brillante
    "#FF55FF",  # 13 magenta brillante
    "#55FFFF",  # 14 cian brillante
    "#FFFFFF",  # 15 blanco
]

FONT_NAME  = "Monospace"
FONT_SIZE  = 14


class AsciiCanvas(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app

        self._font     = tk.font.Font(family=FONT_NAME, size=FONT_SIZE)
        self.cell_w    = self._font.measure("X")
        self.cell_h    = self._font.metrics("linespace")
        self.view_col  = 0   # desplazamiento de vista (scroll)
        self.view_row  = 0
        self._cursor_cell = None  # (col, row) celda bajo el cursor

        self._canvas   = tk.Canvas(self, bg="#000000", cursor="none",
                                   highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        # Diccionario de items: (col, row) → (rect_id, text_id)
        self._items = {}
        # Overlay del cursor (resaltado de celda)
        self._cursor_rect = self._canvas.create_rectangle(
            0, 0, 0, 0, outline="#FFFFFF", width=1, state="hidden"
        )

        self._state = ToolState(self)

        self._canvas.bind("<ButtonPress-1>",   lambda e: self._state.mouse_down(e, 1))
        self._canvas.bind("<ButtonPress-2>",   lambda e: self._state.mouse_down(e, 2))
        self._canvas.bind("<ButtonPress-3>",   lambda e: self._state.mouse_down(e, 3))
        self._canvas.bind("<B1-Motion>",       lambda e: self._state.mouse_move(e))
        self._canvas.bind("<B2-Motion>",       lambda e: self._state.mouse_move(e))
        self._canvas.bind("<Motion>",          lambda e: self._state.mouse_move(e))
        self._canvas.bind("<ButtonRelease-1>", lambda e: self._state.mouse_up(e, 1))
        self._canvas.bind("<ButtonRelease-2>", lambda e: self._state.mouse_up(e, 2))
        self._canvas.bind("<ButtonRelease-3>", lambda e: self._state.mouse_up(e, 3))
        self._canvas.bind("<Leave>",           lambda e: self._state.mouse_leave(e))

    # ── Coordenadas ───────────────────────────────────────────────────────────

    def screen_to_cell(self, sx, sy):
        col = sx // self.cell_w + self.view_col
        row = sy // self.cell_h + self.view_row
        return col, row

    def cell_to_screen(self, col, row):
        x = (col - self.view_col) * self.cell_w
        y = (row - self.view_row) * self.cell_h
        return x, y

    # ── Renderizado ───────────────────────────────────────────────────────────

    def render_frame(self, frame):
        """Redibuja todo el frame actual."""
        self._canvas.delete("cell")
        self._items.clear()
        for row in range(frame.height):
            for col in range(frame.width):
                ch  = frame.content[row][col]
                fg, bg = frame.newColorMap[row][col]
                self._draw_cell(col, row, ch, fg, bg)
        self._canvas.lift(self._cursor_rect)

    def update_cell(self, col, row, ch, fg, bg):
        """Actualiza una sola celda sin redibujar todo el canvas."""
        if (col, row) in self._items:
            rect_id, text_id = self._items[(col, row)]
            x, y = self.cell_to_screen(col, row)
            self._canvas.coords(rect_id, x, y,
                                x + self.cell_w, y + self.cell_h)
            self._canvas.itemconfig(rect_id, fill=ANSI_COLORS[bg % 16])
            self._canvas.coords(text_id, x + self.cell_w // 2,
                                y + self.cell_h // 2)
            self._canvas.itemconfig(text_id, text=ch,
                                    fill=ANSI_COLORS[fg % 16])
        else:
            self._draw_cell(col, row, ch, fg, bg)
        self._canvas.lift(self._cursor_rect)

    def _draw_cell(self, col, row, ch, fg, bg):
        x, y = self.cell_to_screen(col, row)
        rid = self._canvas.create_rectangle(
            x, y, x + self.cell_w, y + self.cell_h,
            fill=ANSI_COLORS[bg % 16], outline="", tags="cell"
        )
        tid = self._canvas.create_text(
            x + self.cell_w // 2, y + self.cell_h // 2,
            text=ch, fill=ANSI_COLORS[fg % 16],
            font=self._font, anchor="center", tags="cell"
        )
        self._items[(col, row)] = (rid, tid)

    # ── Scroll ────────────────────────────────────────────────────────────────

    def set_view(self, col, row):
        frame = self.app.current_frame()
        self.view_col = max(0, min(col, frame.width  - 1))
        self.view_row = max(0, min(row, frame.height - 1))
        self.render_frame(frame)

    # ── Cursor / highlight ────────────────────────────────────────────────────

    def update_cursor(self, event):
        col, row = self.screen_to_cell(event.x, event.y)
        frame = self.app.current_frame()
        if not (0 <= col < frame.width and 0 <= row < frame.height):
            self.clear_cursor_highlight()
            self.app.statusbar.set_pos(None, None)
            return
        self._cursor_cell = (col, row)
        x, y = self.cell_to_screen(col, row)
        self._canvas.coords(self._cursor_rect,
                            x, y, x + self.cell_w, y + self.cell_h)
        self._canvas.itemconfig(self._cursor_rect, state="normal")
        ch  = frame.content[row][col]
        fg, bg = frame.newColorMap[row][col]
        self.app.statusbar.set_pos(col, row, ch, fg, bg)

    def clear_cursor_highlight(self):
        self._cursor_cell = None
        self._canvas.itemconfig(self._cursor_rect, state="hidden")

    # ── Tool callbacks (llamados desde ToolState) ─────────────────────────────

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
