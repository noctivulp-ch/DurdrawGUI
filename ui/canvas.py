import tkinter as tk
import tkinter.font
from tools.base import ToolState
import core.log as log

_log = log.get("canvas")

_EMPTY_CHARS = (" ", "\x00")


# ── Helpers para guías de cel (§7 de la especificación funcional Aseprite) ────

def _cel_bounds(layer, frame_idx):
    """Bounding rect (c0, r0, c1, r1) de todas las celdas no vacías en la capa/frame.
    Devuelve None si la capa está completamente vacía en ese frame."""
    if frame_idx >= len(layer.frames):
        return None
    fr = layer.frame_at(frame_idx)
    c0 = fr.width;  c1 = -1
    r0 = fr.height; r1 = -1
    for r in range(fr.height):
        for c in range(fr.width):
            ch     = fr.content[r][c]
            _fg, bg = fr.newColorMap[r][c]
            if ch not in _EMPTY_CHARS or bg != 0:  # celda opaca (regla de transparencia)
                if c < c0: c0 = c
                if c > c1: c1 = c
                if r < r0: r0 = r
                if r > r1: r1 = r
    return (c0, r0, c1, r1) if c1 >= 0 else None


def _layer_at_cursor(doc, col, row):
    """Capa que aporta el píxel visible en (col, row) — la capa superior con contenido.
    Devuelve la Layer o None si la posición está vacía en todas las capas."""
    fi = doc.current_frame_idx
    for layer in reversed(doc.layers):     # de arriba a abajo (mayor índice = más arriba)
        if not layer.visible or fi >= len(layer.frames):
            continue
        fr = layer.frame_at(fi)
        if not (0 <= row < fr.height and 0 <= col < fr.width):
            continue
        ch     = fr.content[row][col]
        _fg, bg = fr.newColorMap[row][col]
        if ch not in _EMPTY_CHARS or bg != 0:
            return layer
    return None


def _draw_label(c, x, y, text, anchor="center"):
    """Texto con sombra de contraste para legibilidad sobre cualquier fondo."""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        c.create_text(x + dx, y + dy, text=text, fill="#000000",
                      font=("Monospace", 8, "bold"), anchor=anchor, tags="measurement")
    c.create_text(x, y, text=text, fill="#e8e8e8",
                  font=("Monospace", 8, "bold"), anchor=anchor, tags="measurement")

# Re-exportar desde core para mantener compatibilidad con importaciones existentes
from core.color_service import PALETTE_256, ANSI_COLORS  # noqa: F401

_BASE_FONT_SIZE = 14
_ZOOM_STEPS = [6, 8, 10, 12, 14, 16, 18, 20, 24]


class CanvasRenderer:
    """Dibuja frames, celdas y overlays sobre un tk.Canvas. Sin gestión de eventos."""

    def __init__(self, tk_canvas, color_service):
        self._c   = tk_canvas
        self._svc = color_service
        self._font = None
        self.cell_w   = 0
        self.cell_h   = 0
        self.view_col = 0
        self.view_row = 0
        self._items      = {}
        self._cursor_box = None
        self._sel_box    = None
        self._paste_box  = None

    def set_font(self, font, cell_w, cell_h):
        self._font  = font
        self.cell_w = cell_w
        self.cell_h = cell_h

    # ── Coordenadas ───────────────────────────────────────────────────────

    def screen_to_cell(self, sx, sy):
        return sx // self.cell_w + self.view_col, sy // self.cell_h + self.view_row

    def cell_to_screen(self, col, row):
        return (col - self.view_col) * self.cell_w, (row - self.view_row) * self.cell_h

    # ── Renderizado de frame ───────────────────────────────────────────────

    def render_frame(self, frame, show_grid=False):
        c = self._c
        # Borrar todo de una vez (incluyendo overlays acumulados de renders anteriores)
        c.delete("all")
        self._items.clear()
        self._cursor_box = None
        self._sel_box    = None
        self._paste_box  = None

        for row in range(frame.height):
            for col in range(frame.width):
                self._draw_cell(col, row,
                                frame.content[row][col],
                                *frame.newColorMap[row][col])

        # Borde delimitador del documento
        self._draw_doc_border(frame)

        if show_grid:
            self._draw_grid(frame)

        # Overlays: cursor, selección, paste — se crean UNA VEZ por render
        self._cursor_box = c.create_rectangle(
            0, 0, 0, 0, outline="#FFFFFF", width=1, state="hidden", tags="overlay"
        )
        self._sel_box = c.create_rectangle(
            0, 0, 0, 0, outline="#FFFF00", width=1,
            dash=(4, 3), state="hidden", tags="overlay"
        )
        self._paste_box = c.create_rectangle(
            0, 0, 0, 0, outline="#00FF88", width=1,
            dash=(4, 3), state="hidden", tags="overlay"
        )

    def update_cell(self, col, row, ch, fg, bg):
        if (col, row) in self._items:
            rid, tid = self._items[(col, row)]
            x, y = self.cell_to_screen(col, row)
            c = self._c
            c.coords(rid, x, y, x + self.cell_w, y + self.cell_h)
            c.itemconfig(rid, fill=self._svc.color(bg))
            c.coords(tid, x + self.cell_w // 2, y + self.cell_h // 2)
            c.itemconfig(tid, text=ch, fill=self._svc.color(fg), font=self._font)
        else:
            self._draw_cell(col, row, ch, fg, bg)
        self._c.lift("overlay")

    def _draw_cell(self, col, row, ch, fg, bg):
        x, y = self.cell_to_screen(col, row)
        c = self._c
        rid = c.create_rectangle(
            x, y, x + self.cell_w, y + self.cell_h,
            fill=self._svc.color(bg), outline="", tags="cell"
        )
        tid = c.create_text(
            x + self.cell_w // 2, y + self.cell_h // 2,
            text=ch, fill=self._svc.color(fg),
            font=self._font, anchor="center", tags="cell"
        )
        self._items[(col, row)] = (rid, tid)

    def _draw_doc_border(self, frame):
        """Rectángulo delimitador en el borde del área dibujable."""
        x0, y0 = self.cell_to_screen(0, 0)
        x1, y1 = self.cell_to_screen(frame.width, frame.height)
        self._c.create_rectangle(
            x0, y0, x1 - 1, y1 - 1,
            outline="#555555", fill="", width=1, tags="docborder"
        )

    def _draw_grid(self, frame):
        """Cuadrícula alineada con las celdas, respetando la posición de vista."""
        x0, y0 = self.cell_to_screen(0, 0)
        w = frame.width  * self.cell_w
        h = frame.height * self.cell_h
        c = self._c
        for col in range(frame.width + 1):
            x = x0 + col * self.cell_w
            c.create_line(x, y0, x, y0 + h, fill="#2a2a2a", tags="grid")
        for row in range(frame.height + 1):
            y = y0 + row * self.cell_h
            c.create_line(x0, y, x0 + w, y, fill="#2a2a2a", tags="grid")

    # ── Preview (rubber-band) ──────────────────────────────────────────────

    def draw_preview(self, cells):
        self._c.delete("preview")
        for col, row, ch in cells:
            x, y = self.cell_to_screen(col, row)
            self._c.create_text(
                x + self.cell_w // 2, y + self.cell_h // 2,
                text=ch, fill="#00FF88",
                font=self._font, anchor="center", tags="preview"
            )
        self._c.lift("overlay")

    def clear_preview(self):
        self._c.delete("preview")

    # ── Overlays (cursor, selección, paste) ───────────────────────────────

    def update_cursor_overlay(self, col, row):
        x, y = self.cell_to_screen(col, row)
        if self._cursor_box:
            self._c.coords(self._cursor_box, x, y, x + self.cell_w, y + self.cell_h)
            self._c.itemconfig(self._cursor_box, state="normal")

    def hide_cursor_overlay(self):
        if self._cursor_box:
            self._c.itemconfig(self._cursor_box, state="hidden")

    def show_selection(self, c0, r0, c1, r1):
        if not self._sel_box:
            return
        x0, y0 = self.cell_to_screen(c0, r0)
        x1, y1 = self.cell_to_screen(c1 + 1, r1 + 1)
        self._c.coords(self._sel_box, x0, y0, x1, y1)
        self._c.itemconfig(self._sel_box, state="normal")

    def hide_selection(self):
        if self._sel_box:
            self._c.itemconfig(self._sel_box, state="hidden")
        if self._paste_box:
            self._c.itemconfig(self._paste_box, state="hidden")

    # ── Guías automáticas de cel (Ctrl) ───────────────────────────────────

    def draw_cel_guides(self, doc, col, row):
        """Guías automáticas de cel al mantener Ctrl (§7 de la especificación Aseprite).

        - Dibuja el bounds rect del cel de la capa activa (azul opaco).
        - Detecta qué capa aporta el píxel visible bajo el cursor.
        - Si es distinta de la activa: dibuja su bounds rect (azul claro, punteado)
          y las guías de medición entre ambos.
        - Si el cursor está sobre área vacía: guías desde el cel activo al lienzo.
        - Si el cursor está sobre la misma capa activa: sin guías (solo bounds activo).
        """
        c = self._c
        c.delete("measurement")

        fi = doc.current_frame_idx

        # ── Bounds del cel activo ──────────────────────────────────────────
        bounds_a = _cel_bounds(doc.active_layer, fi)

        # ── Capa y bounds bajo el cursor ───────────────────────────────────
        target_layer = _layer_at_cursor(doc, col, row)
        same_layer   = (target_layer is doc.active_layer)

        if same_layer:
            bounds_t = None
            ref      = None          # misma capa → sin guías
        elif target_layer is None:
            bounds_t = None
            ref      = (0, 0, doc.width - 1, doc.height - 1)   # área vacía → mide al canvas
        else:
            bounds_t = _cel_bounds(target_layer, fi)
            ref      = bounds_t if bounds_t else (0, 0, doc.width - 1, doc.height - 1)

        COLOR_A     = "#4488ff"   # bounds capa activa (opaco)
        COLOR_T     = "#88aaff"   # bounds capa objetivo (claro, simula semi-transparencia)
        COLOR_GUIDE = "#4488ff"

        # Rectángulo del cel activo
        if bounds_a:
            sx0, sy0 = self.cell_to_screen(bounds_a[0], bounds_a[1])
            sx1, sy1 = self.cell_to_screen(bounds_a[2] + 1, bounds_a[3] + 1)
            c.create_rectangle(sx0, sy0, sx1 - 1, sy1 - 1,
                               outline=COLOR_A, width=1, tags="measurement")

        # Rectángulo del cel objetivo (si existe y es distinta capa)
        if bounds_t:
            tx0, ty0 = self.cell_to_screen(bounds_t[0], bounds_t[1])
            tx1, ty1 = self.cell_to_screen(bounds_t[2] + 1, bounds_t[3] + 1)
            c.create_rectangle(tx0, ty0, tx1 - 1, ty1 - 1,
                               outline=COLOR_T, width=1, dash=(3, 2), tags="measurement")

        # Guías de medición entre bounds_a y ref
        if bounds_a and ref is not None:
            self._draw_axis_guides_x(bounds_a, ref, COLOR_GUIDE)
            self._draw_axis_guides_y(bounds_a, ref, COLOR_GUIDE)

        c.lift("overlay")

    def _draw_axis_guides_x(self, bounds_a, bounds_r, color):
        """Guías horizontales que miden separación/desalineación en el eje X."""
        c = self._c
        a_lo, a_hi = bounds_a[0], bounds_a[2]
        r_lo, r_hi = bounds_r[0], bounds_r[2]

        # Centro vertical del cel activo en pantalla (posición Y de la línea guía)
        center_y = (self.cell_to_screen(0, bounds_a[1])[1] +
                    self.cell_to_screen(0, bounds_a[3] + 1)[1]) // 2

        # Rango Y del rect de referencia (para decidir si necesita conector)
        ref_y0 = self.cell_to_screen(0, bounds_r[1])[1]
        ref_y1 = self.cell_to_screen(0, bounds_r[3] + 1)[1]

        def px_lo(col): return self.cell_to_screen(col, 0)[0]      # borde izq de celda col
        def px_hi(col): return self.cell_to_screen(col + 1, 0)[0]  # borde der de celda col

        def guide(px_from, px_to, dist):
            if dist <= 0 or px_from >= px_to:
                return
            c.create_line(px_from, center_y, px_to, center_y,
                          fill=color, width=1, tags="measurement")
            _draw_label(c, (px_from + px_to) // 2, center_y - 10, str(dist))

        def connector(px_x):
            """Conector vertical al borde Y del rect de referencia si center_y está fuera."""
            if center_y < ref_y0:
                c.create_line(px_x, center_y, px_x, ref_y0,
                              fill=color, dash=(4, 3), tags="measurement")
            elif center_y > ref_y1:
                c.create_line(px_x, center_y, px_x, ref_y1,
                              fill=color, dash=(4, 3), tags="measurement")

        overlapping = a_lo <= r_hi and a_hi >= r_lo
        if not overlapping:
            if a_hi < r_lo:             # A completamente a la izquierda de R
                guide(px_hi(a_hi), px_lo(r_lo), r_lo - a_hi - 1)
                connector(px_lo(r_lo))
            else:                       # A completamente a la derecha de R
                guide(px_hi(r_hi), px_lo(a_lo), a_lo - r_hi - 1)
                connector(px_hi(r_hi))
        else:                           # Se solapan: guías por bordes desalineados
            if a_lo != r_lo:
                guide(px_lo(min(a_lo, r_lo)), px_lo(max(a_lo, r_lo)), abs(a_lo - r_lo))
                connector(px_lo(r_lo))
            if a_hi != r_hi:
                guide(px_hi(min(a_hi, r_hi)), px_hi(max(a_hi, r_hi)), abs(a_hi - r_hi))
                connector(px_hi(r_hi))

    def _draw_axis_guides_y(self, bounds_a, bounds_r, color):
        """Guías verticales que miden separación/desalineación en el eje Y."""
        c = self._c
        a_lo, a_hi = bounds_a[1], bounds_a[3]
        r_lo, r_hi = bounds_r[1], bounds_r[3]

        center_x = (self.cell_to_screen(bounds_a[0], 0)[0] +
                    self.cell_to_screen(bounds_a[2] + 1, 0)[0]) // 2

        ref_x0 = self.cell_to_screen(bounds_r[0], 0)[0]
        ref_x1 = self.cell_to_screen(bounds_r[2] + 1, 0)[0]

        def py_lo(row): return self.cell_to_screen(0, row)[1]
        def py_hi(row): return self.cell_to_screen(0, row + 1)[1]

        def guide(py_from, py_to, dist):
            if dist <= 0 or py_from >= py_to:
                return
            c.create_line(center_x, py_from, center_x, py_to,
                          fill=color, width=1, tags="measurement")
            _draw_label(c, center_x + 7, (py_from + py_to) // 2, str(dist), anchor="w")

        def connector(py_y):
            if center_x < ref_x0:
                c.create_line(center_x, py_y, ref_x0, py_y,
                              fill=color, dash=(4, 3), tags="measurement")
            elif center_x > ref_x1:
                c.create_line(center_x, py_y, ref_x1, py_y,
                              fill=color, dash=(4, 3), tags="measurement")

        overlapping = a_lo <= r_hi and a_hi >= r_lo
        if not overlapping:
            if a_hi < r_lo:
                guide(py_hi(a_hi), py_lo(r_lo), r_lo - a_hi - 1)
                connector(py_lo(r_lo))
            else:
                guide(py_hi(r_hi), py_lo(a_lo), a_lo - r_hi - 1)
                connector(py_hi(r_hi))
        else:
            if a_lo != r_lo:
                guide(py_lo(min(a_lo, r_lo)), py_lo(max(a_lo, r_lo)), abs(a_lo - r_lo))
                connector(py_lo(r_lo))
            if a_hi != r_hi:
                guide(py_hi(min(a_hi, r_hi)), py_hi(max(a_hi, r_hi)), abs(a_hi - r_hi))
                connector(py_hi(r_hi))

    def hide_measurements(self):
        self._c.delete("measurement")

    def show_paste_preview(self, col, row, n_rows, n_cols):
        if not self._paste_box:
            return
        x0, y0 = self.cell_to_screen(col, row)
        x1, y1 = self.cell_to_screen(col + n_cols, row + n_rows)
        self._c.coords(self._paste_box, x0, y0, x1, y1)
        self._c.itemconfig(self._paste_box, state="normal")

    # ── Cursor de pincel (footprint) ───────────────────────────────────────

    def draw_brush_cursor(self, col, row, cells, ch, fg_idx, bg_idx, color_svc=None):
        """Renderiza el footprint del pincel bajo el cursor como overlay semitransparente.

        Cada celda del brush se dibuja con stipple='gray50' para simular transparencia;
        el carácter activo se superpone en el centro de cada celda pintada.
        """
        svc = color_svc if color_svc is not None else self._svc
        c = self._c
        c.delete("brush_cursor")

        fg_color = svc.color(fg_idx)
        bg_color = svc.color(bg_idx)

        for dr, dc in cells:
            r, col_c = row + dr, col + dc
            x, y = self.cell_to_screen(col_c, r)
            # Fondo semi-opaco (stipple simula ~50 % de transparencia)
            c.create_rectangle(
                x, y, x + self.cell_w, y + self.cell_h,
                fill=bg_color, outline="#aaaaaa", width=1,
                stipple="gray50", tags="brush_cursor",
            )
            # Carácter del pincel
            if ch and ch not in (" ", "\x00"):
                c.create_text(
                    x + self.cell_w // 2, y + self.cell_h // 2,
                    text=ch, fill=fg_color,
                    font=self._font, anchor="center",
                    tags="brush_cursor",
                )
        c.lift("overlay")

    def hide_brush_cursor(self):
        self._c.delete("brush_cursor")


class AsciiCanvas(tk.Frame):
    """Widget principal del lienzo. Gestiona eventos de ratón/teclado y
    delega todo el dibujado a CanvasRenderer. Siempre renderiza el compuesto
    de todas las capas del documento activo."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app

        self._zoom_idx    = _ZOOM_STEPS.index(_BASE_FONT_SIZE)
        self._cursor_cell = None
        self._sel_rect    = None
        self._ctrl_held   = False

        self._canvas = tk.Canvas(self, bg="#000000", cursor="none",
                                 highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._renderer = CanvasRenderer(self._canvas, app.color_service)
        self._state    = ToolState(self)
        self._apply_zoom()
        self._bind_events()

        # Re-dibujar cuando cambia el modo de color
        app.bus.on("color_mode_changed", lambda _: self.render_frame())

    # ── Propiedades proxy (ToolState y código externo los acceden) ─────────

    @property
    def cell_w(self):
        return self._renderer.cell_w

    @property
    def cell_h(self):
        return self._renderer.cell_h

    @property
    def view_col(self):
        return self._renderer.view_col

    @view_col.setter
    def view_col(self, v):
        self._renderer.view_col = v

    @property
    def view_row(self):
        return self._renderer.view_row

    @view_row.setter
    def view_row(self, v):
        self._renderer.view_row = v

    # ── Zoom ──────────────────────────────────────────────────────────────

    def _apply_zoom(self):
        size  = _ZOOM_STEPS[self._zoom_idx]
        font  = tk.font.Font(family="Monospace", size=size)
        self._renderer.set_font(font, font.measure("X"), font.metrics("linespace"))
        pct   = int(size / _BASE_FONT_SIZE * 100)
        if hasattr(self, 'app') and self.app and hasattr(self.app, 'context_bar'):
            self.app.context_bar.set_zoom(pct)
        return pct

    def zoom_in(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx < len(_ZOOM_STEPS) - 1:
            self._zoom_idx += 1
            self._apply_zoom_anchored(mouse_x, mouse_y)
            self.render_frame()
        return int(_ZOOM_STEPS[self._zoom_idx] / _BASE_FONT_SIZE * 100)

    def zoom_out(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx > 0:
            self._zoom_idx -= 1
            self._apply_zoom_anchored(mouse_x, mouse_y)
            self.render_frame()
        return int(_ZOOM_STEPS[self._zoom_idx] / _BASE_FONT_SIZE * 100)

    def zoom_reset(self):
        self._zoom_idx = _ZOOM_STEPS.index(_BASE_FONT_SIZE)
        self._apply_zoom()
        self.render_frame()
        return 100

    def _apply_zoom_anchored(self, mouse_x, mouse_y):
        """Aplica el zoom nuevo y ajusta view_col/row para anclar el cursor."""
        old_cw = self._renderer.cell_w
        old_ch = self._renderer.cell_h
        old_vc = self._renderer.view_col
        old_vr = self._renderer.view_row
        self._apply_zoom()
        if mouse_x is None:
            return
        new_cw = self._renderer.cell_w
        new_ch = self._renderer.cell_h
        # Celda bajo cursor antes del zoom: cell_col = mouse_x / old_cw + old_vc
        # Queremos que permanezca en mouse_x: mouse_x / new_cw + new_vc = cell_col
        new_vc = old_vc + mouse_x * (1 / old_cw - 1 / new_cw)
        new_vr = old_vr + mouse_y * (1 / old_ch - 1 / new_ch)
        doc = self.app.doc
        # Permitir negativos para que el documento pueda quedar offset en el viewport
        self._renderer.view_col = min(int(new_vc), max(0, doc.width  - 1))
        self._renderer.view_row = min(int(new_vr), max(0, doc.height - 1))

    # ── Coordenadas ───────────────────────────────────────────────────────

    def screen_to_cell(self, sx, sy):
        return self._renderer.screen_to_cell(sx, sy)

    def cell_to_screen(self, col, row):
        return self._renderer.cell_to_screen(col, row)

    # ── Renderizado — siempre usa el compuesto del documento ──────────────

    def render_frame(self, _frame=None):
        """Renderiza el compuesto de todas las capas visibles."""
        composite = self.app.doc.composite_frame()
        _log.debug(f"render_frame  {composite.width}×{composite.height}")
        self._renderer.render_frame(composite, getattr(self.app, '_show_grid', False))

    def update_cell(self, col, row, _ch=None, _fg=None, _bg=None):
        """Actualiza una celda con el compuesto del documento en esa posición."""
        comp_ch, comp_fg, comp_bg = self.app.doc.composite_cell(col, row)
        self._renderer.update_cell(col, row, comp_ch, comp_fg, comp_bg)

    def draw_preview(self, cells):
        self._renderer.draw_preview(cells)

    def clear_preview(self):
        self._renderer.clear_preview()

    # ── Scroll / vista ────────────────────────────────────────────────────

    def set_view(self, col, row):
        doc = self.app.doc
        # Sin límite inferior: view negativo permite ver el documento desplazado a la derecha/abajo
        # Límite superior: no alejarse más de un viewport del borde derecho/inferior
        self._renderer.view_col = min(col, max(0, doc.width  - 1))
        self._renderer.view_row = min(row, max(0, doc.height - 1))
        self.render_frame()

    # ── Cursor ────────────────────────────────────────────────────────────

    def _ctrl_pressed(self, held):
        """Activa/desactiva el modo de guías automáticas de cel."""
        self._ctrl_held = held
        if not held:
            self._renderer.hide_measurements()
        elif self._cursor_cell:
            col, row = self._cursor_cell
            self._renderer.draw_cel_guides(self.app.doc, col, row)

    def update_cursor(self, event):
        col, row = self.screen_to_cell(event.x, event.y)
        doc = self.app.doc
        if not (0 <= col < doc.width and 0 <= row < doc.height):
            self.clear_cursor_highlight()
            self._renderer.hide_measurements()
            self.app.statusbar.set_pos(None, None)
            if not self._state._space_held:
                self._canvas.config(cursor="crosshair")
            return
        if not self._state._space_held:
            self._canvas.config(cursor="none")
        self._cursor_cell = (col, row)

        # Cursor de pincel cuando la herramienta activa usa 'brush'
        is_brush_tool = getattr(self.app.active_tool, "context_key", None) == "brush"
        if is_brush_tool:
            brush = self.app.active_brush
            self._renderer.draw_brush_cursor(
                col, row, brush.cells,
                self.app.fg_char, self.app.fg_color, self.app.bg_color,
                self.app.color_service,
            )
            self._renderer.hide_cursor_overlay()
        else:
            self._renderer.hide_brush_cursor()
            self._renderer.update_cursor_overlay(col, row)

        ch, fg, bg = doc.composite_cell(col, row)
        self.app.statusbar.set_pos(col, row, ch, fg, bg)
        if self._ctrl_held:
            self._renderer.draw_cel_guides(doc, col, row)
        if self.app.clipboard is not None and self.app.active_tool.name == "selection":
            self._update_paste_preview(col, row)

    def clear_cursor_highlight(self):
        self._cursor_cell = None
        self._renderer.hide_cursor_overlay()
        self._renderer.hide_brush_cursor()

    # ── Selección visual ──────────────────────────────────────────────────

    def set_selection(self, c0, r0, c1, r1):
        self._sel_rect = (c0, r0, c1, r1)
        self._renderer.show_selection(c0, r0, c1, r1)

    def clear_selection(self):
        self._sel_rect = None
        self._renderer.hide_selection()

    def _update_paste_preview(self, col, row):
        if not self.app.clipboard:
            return
        n_rows = len(self.app.clipboard)
        n_cols = len(self.app.clipboard[0]) if n_rows else 0
        self._renderer.show_paste_preview(col, row, n_rows, n_cols)

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

    # ── Bindings ──────────────────────────────────────────────────────────

    def _bind_events(self):
        c = self._canvas
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
        # Ctrl global: capturar desde la ventana raíz para que funcione sin foco en el canvas
        root = self.app.root
        root.bind("<KeyPress-Control_L>",   lambda e: self._ctrl_pressed(True),  add="+")
        root.bind("<KeyPress-Control_R>",   lambda e: self._ctrl_pressed(True),  add="+")
        root.bind("<KeyRelease-Control_L>", lambda e: self._ctrl_pressed(False), add="+")
        root.bind("<KeyRelease-Control_R>", lambda e: self._ctrl_pressed(False), add="+")
