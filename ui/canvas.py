"""
ui_qt/canvas.py — lienzo ASCII/ANSI nativo Qt/Wayland.

Reemplaza ui/canvas.py (Tkinter).  Todo el dibujo ocurre en paintEvent()
con QPainter; no hay ítems Tk, no hay tags, no hay grab X11.

API pública idéntica a la versión Tkinter para que tools/ y app.py no cambien:
    render_frame()
    update_cell(col, row)
    update_cursor(col, row)        ← ahora recibe col/row en lugar del event Tk
    clear_cursor_highlight()
    draw_cel_guides(doc, col, row)
    draw_brush_cursor(col, row, cells, ch, fg, bg, color_svc)
    hide_brush_cursor()
    draw_preview(cells)
    clear_preview()
    set_selection(c0, r0, c1, r1)
    clear_selection()
    set_view(col, row)
    zoom_in/out/reset()
    cell_w, cell_h, view_col, view_row  (propiedades)
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore    import Qt, QRect, QPoint, QTimer
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QFontMetrics,
    QPaintEvent, QMouseEvent, QWheelEvent, QKeyEvent,
)

import core.log as log

_log = log.get("canvas_qt")

# ── Paleta ANSI 16 colores (compatibilidad con core/color_service.py) ─────────
ANSI_COLORS = [
    "#000000", "#aa0000", "#00aa00", "#aa5500",
    "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
]

# ── Niveles de zoom ────────────────────────────────────────────────────────────
_ZOOM_STEPS    = [6, 8, 10, 12, 14, 16, 18, 20, 24]
_BASE_FONT_IDX = _ZOOM_STEPS.index(14)

# ── Estados de la herramienta ──────────────────────────────────────────────────
_STANDBY   = "standby"
_DRAWING   = "drawing"
_SCROLLING = "scrolling"

# ── Helpers para guías de cel (§7) ────────────────────────────────────────────

_EMPTY_CHARS = (" ", "\x00")


def _cel_bounds(layer, frame_idx):
    if frame_idx >= len(layer.frames):
        return None
    fr = layer.frame_at(frame_idx)
    c0 = fr.width;  c1 = -1
    r0 = fr.height; r1 = -1
    for r in range(fr.height):
        for c in range(fr.width):
            ch      = fr.content[r][c]
            _fg, bg = fr.newColorMap[r][c]
            if ch not in _EMPTY_CHARS or bg != 0:
                if c < c0: c0 = c
                if c > c1: c1 = c
                if r < r0: r0 = r
                if r > r1: r1 = r
    return (c0, r0, c1, r1) if c1 >= 0 else None


def _layer_at_cursor(doc, col, row):
    fi = doc.current_frame_idx
    for layer in reversed(doc.layers):
        if not layer.visible or fi >= len(layer.frames):
            continue
        fr = layer.frame_at(fi)
        if not (0 <= row < fr.height and 0 <= col < fr.width):
            continue
        ch      = fr.content[row][col]
        _fg, bg = fr.newColorMap[row][col]
        if ch not in _EMPTY_CHARS or bg != 0:
            return layer
    return None


def _qcolor(idx: int, svc=None) -> QColor:
    """Convierte un índice de paleta a QColor."""
    if svc is not None:
        hex_str = svc.color(idx)   # devuelve "#rrggbb"
        return QColor(hex_str)
    if 0 <= idx < len(ANSI_COLORS):
        return QColor(ANSI_COLORS[idx])
    return QColor("#000000")


# ══════════════════════════════════════════════════════════════════════════════
class AsciiCanvas(QWidget):
    """Lienzo ASCII/ANSI nativo Wayland.

    Toda la lógica de dibujo vive en paintEvent(); el estado de los overlays
    (cursor, selección, guías, brush) se guarda como atributos y se refresca
    con self.update() en lugar de manipular ítems de un canvas Tkinter.
    """

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app

        # ── Zoom ──────────────────────────────────────────────────────────
        self._zoom_idx = _BASE_FONT_IDX
        self._font     = QFont("Monospace", _ZOOM_STEPS[_BASE_FONT_IDX])
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setFixedPitch(True)
        self._recalc_cell_size()

        # ── Vista (scroll) ─────────────────────────────────────────────────
        self._view_col = 0
        self._view_row = 0

        # ── Estado de la herramienta activa ────────────────────────────────
        self._tool_state    = _STANDBY
        self._scroll_origin: tuple[int, int] | None = None
        self._scroll_view_orig: tuple[int, int] | None = None
        self._space_held    = False
        self._ctrl_held     = False
        self._saved_tool    = None

        # ── Overlays (toda la info necesaria para paintEvent) ──────────────
        self._cursor_cell:   tuple[int, int] | None = None
        self._cursor_vis     = False
        self._sel_rect:      tuple[int, int, int, int] | None = None
        self._paste_preview: tuple[int, int, int, int] | None = None
        self._brush_cursor:  tuple | None = None   # (col, row, cells, ch, fg, bg)
        self._preview_cells: list | None = None    # [(col, row, ch), ...]
        self._cel_guides_pos: tuple[int, int] | None = None  # col, row bajo cursor

        # ── Foco y tamaño ─────────────────────────────────────────────────
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setStyleSheet("background-color: #000000;")

        # Rerender al cambiar modo de color
        app.bus.on("color_mode_changed", lambda _: self.update())

        _log.debug("AsciiCanvas Qt inicializado")

    # ── Propiedades proxy (misma API que versión Tkinter) ─────────────────

    @property
    def cell_w(self) -> int:
        return self._cell_w

    @property
    def cell_h(self) -> int:
        return self._cell_h

    @property
    def view_col(self) -> int:
        return self._view_col

    @view_col.setter
    def view_col(self, v: int):
        self._view_col = v

    @property
    def view_row(self) -> int:
        return self._view_row

    @view_row.setter
    def view_row(self, v: int):
        self._view_row = v

    # ── Coordenadas ───────────────────────────────────────────────────────

    def _recalc_cell_size(self):
        fm = QFontMetrics(self._font)
        self._cell_w = fm.horizontalAdvance("X")
        self._cell_h = fm.height()
        self._fm_ascent = fm.ascent()

    def screen_to_cell(self, sx: int, sy: int) -> tuple[int, int]:
        return (int(sx) // self._cell_w + self._view_col,
                int(sy) // self._cell_h + self._view_row)

    def cell_to_screen(self, col: int, row: int) -> tuple[int, int]:
        return (col - self._view_col) * self._cell_w, (row - self._view_row) * self._cell_h

    # ── Zoom ──────────────────────────────────────────────────────────────

    def _apply_zoom(self):
        size = _ZOOM_STEPS[self._zoom_idx]
        self._font = QFont("Monospace", size)
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setFixedPitch(True)
        self._recalc_cell_size()
        pct = int(size / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)
        if hasattr(self.app, "context_bar"):
            self.app.context_bar.set_zoom(pct)
        return pct

    def zoom_in(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx < len(_ZOOM_STEPS) - 1:
            self._zoom_anchored(self._zoom_idx + 1, mouse_x, mouse_y)
        return int(_ZOOM_STEPS[self._zoom_idx] / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)

    def zoom_out(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx > 0:
            self._zoom_anchored(self._zoom_idx - 1, mouse_x, mouse_y)
        return int(_ZOOM_STEPS[self._zoom_idx] / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)

    def zoom_reset(self):
        self._zoom_idx = _BASE_FONT_IDX
        self._apply_zoom()
        self.update()
        return 100

    def _zoom_anchored(self, new_idx: int, mx, my):
        old_cw, old_ch = self._cell_w, self._cell_h
        old_vc, old_vr = self._view_col, self._view_row
        self._zoom_idx = new_idx
        self._apply_zoom()
        if mx is not None and my is not None:
            new_vc = old_vc + mx * (1 / old_cw - 1 / self._cell_w)
            new_vr = old_vr + my * (1 / old_ch - 1 / self._cell_h)
            doc = self.app.doc
            self._view_col = min(int(new_vc), max(0, doc.width  - 1))
            self._view_row = min(int(new_vr), max(0, doc.height - 1))
        self.update()

    # ── API pública de renderizado ─────────────────────────────────────────

    def render_frame(self, _frame=None):
        _log.debug(f"render_frame  {self.app.doc.width}×{self.app.doc.height}")
        self.update()

    def update_cell(self, col, row, _ch=None, _fg=None, _bg=None):
        # En Qt un update() por región sería óptimo; por ahora refrescamos todo
        self.update()

    def set_view(self, col: int, row: int):
        doc = self.app.doc
        self._view_col = int(min(col, max(0, doc.width  - 1)))
        self._view_row = int(min(row, max(0, doc.height - 1)))
        self.update()

    # ── Overlays — setters que disparan update() ──────────────────────────

    def update_cursor(self, col: int, row: int):
        """Actualiza el cursor y los overlays dinámicos. Recibe col/row directamente."""
        doc = self.app.doc
        if not (0 <= col < doc.width and 0 <= row < doc.height):
            self.clear_cursor_highlight()
            if hasattr(self.app, "statusbar"):
                self.app.statusbar.set_pos(None, None)
            return

        self._cursor_cell = (col, row)
        is_brush = getattr(self.app.active_tool, "context_key", None) == "brush"

        if is_brush:
            brush = self.app.active_brush
            self._brush_cursor = (col, row, brush.cells,
                                  self.app.fg_char, self.app.fg_color, self.app.bg_color)
            self._cursor_vis = False
        else:
            self._brush_cursor = None
            self._cursor_vis   = True

        if self._ctrl_held:
            self._cel_guides_pos = (col, row)
        else:
            self._cel_guides_pos = None

        ch, fg, bg = doc.composite_cell(col, row)
        if hasattr(self.app, "statusbar"):
            self.app.statusbar.set_pos(col, row, ch, fg, bg)

        if (self.app.clipboard is not None
                and self.app.active_tool.name == "selection"):
            n_rows = len(self.app.clipboard)
            n_cols = len(self.app.clipboard[0]) if n_rows else 0
            self._paste_preview = (col, row, n_rows, n_cols)
        else:
            self._paste_preview = None

        self.update()

    def clear_cursor_highlight(self):
        self._cursor_cell    = None
        self._cursor_vis     = False
        self._brush_cursor   = None
        self._cel_guides_pos = None
        self.update()

    def draw_cel_guides(self, doc, col, row):
        self._cel_guides_pos = (col, row)
        self.update()

    def draw_brush_cursor(self, col, row, cells, ch, fg_idx, bg_idx, color_svc=None):
        self._brush_cursor = (col, row, cells, ch, fg_idx, bg_idx)
        self._cursor_vis   = False
        self.update()

    def hide_brush_cursor(self):
        self._brush_cursor = None
        self.update()

    def draw_preview(self, cells):
        self._preview_cells = cells
        self.update()

    def clear_preview(self):
        self._preview_cells = None
        self.update()

    def set_selection(self, c0, r0, c1, r1):
        self._sel_rect = (c0, r0, c1, r1)
        self.update()

    def clear_selection(self):
        self._sel_rect = None
        self.update()

    # ── paintEvent — todo el dibujo del lienzo ────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        try:
            self._do_paint(painter, event)
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            painter.end()

    def _do_paint(self, painter: QPainter, event: QPaintEvent):
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        painter.setFont(self._font)

        doc  = self.app.doc
        svc  = self.app.color_service
        show_grid = getattr(self.app, "_show_grid", False)

        frame = doc.composite_frame()
        cw, ch = self._cell_w, self._cell_h

        # ── Celdas ────────────────────────────────────────────────────────
        widget_w = self.width()
        widget_h = self.height()
        visible_cols = widget_w // cw + 2
        visible_rows = widget_h // ch + 2

        vc_off = int(self._view_col)
        vr_off = int(self._view_row)

        for vr in range(visible_rows):
            row = vr + vr_off
            if row < 0 or row >= frame.height:
                continue
            for vc in range(visible_cols):
                col = vc + vc_off
                if col < 0 or col >= frame.width:
                    continue
                cell_ch      = frame.content[row][col]
                fg_idx, bg_idx = frame.newColorMap[row][col]
                x = vc * cw
                y = vr * ch
                painter.fillRect(x, y, cw, ch, _qcolor(bg_idx, svc))
                if cell_ch and cell_ch not in _EMPTY_CHARS:
                    painter.setPen(_qcolor(fg_idx, svc))
                    painter.drawText(QRect(x, y, cw, ch), Qt.AlignmentFlag.AlignCenter, cell_ch)

        # ── Borde del documento ───────────────────────────────────────────
        self._paint_doc_border(painter, frame, cw, ch)

        # ── Rejilla opcional ──────────────────────────────────────────────
        if show_grid:
            self._paint_grid(painter, frame, cw, ch)

        # ── Preview (rubber-band de herramientas de forma) ─────────────────
        if self._preview_cells:
            painter.setPen(QColor("#00FF88"))
            for p_col, p_row, p_ch in self._preview_cells:
                x, y = self.cell_to_screen(p_col, p_row)
                painter.drawText(QRect(x, y, cw, ch), Qt.AlignmentFlag.AlignCenter, p_ch)

        # ── Guías de cel (Ctrl) ────────────────────────────────────────────
        if self._ctrl_held and self._cel_guides_pos:
            self._paint_cel_guides(painter, doc, *self._cel_guides_pos, cw, ch)

        # ── Selección ─────────────────────────────────────────────────────
        if self._sel_rect:
            c0, r0, c1, r1 = self._sel_rect
            x0, y0 = self.cell_to_screen(c0, r0)
            x1, y1 = self.cell_to_screen(c1 + 1, r1 + 1)
            pen = QPen(QColor("#FFFF00"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        # ── Preview de paste ───────────────────────────────────────────────
        if self._paste_preview:
            p_col, p_row, n_rows, n_cols = self._paste_preview
            x0, y0 = self.cell_to_screen(p_col, p_row)
            x1, y1 = self.cell_to_screen(p_col + n_cols, p_row + n_rows)
            pen = QPen(QColor("#00FF88"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        # ── Brush cursor (footprint semitransparente) ──────────────────────
        if self._brush_cursor:
            self._paint_brush_cursor(painter, svc, cw, ch)

        # ── Cursor de celda ───────────────────────────────────────────────
        if self._cursor_vis and self._cursor_cell:
            col, row = self._cursor_cell
            x, y = self.cell_to_screen(col, row)
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, cw - 1, ch - 1)

    # ── Helpers de paintEvent ─────────────────────────────────────────────

    def _paint_doc_border(self, painter, frame, cw, ch):
        x0, y0 = self.cell_to_screen(0, 0)
        x1, y1 = self.cell_to_screen(frame.width, frame.height)
        painter.setPen(QPen(QColor("#555555"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(x0, y0, x1 - x0 - 1, y1 - y0 - 1)

    def _paint_grid(self, painter, frame, cw, ch):
        x0, y0 = self.cell_to_screen(0, 0)
        w = frame.width  * cw
        h = frame.height * ch
        painter.setPen(QPen(QColor("#2a2a2a"), 1))
        for col in range(frame.width + 1):
            x = x0 + col * cw
            painter.drawLine(x, y0, x, y0 + h)
        for row in range(frame.height + 1):
            y = y0 + row * ch
            painter.drawLine(x0, y, x0 + w, y)

    def _paint_brush_cursor(self, painter, svc, cw, ch):
        col, row, cells, cell_ch, fg_idx, bg_idx = self._brush_cursor
        fg = _qcolor(fg_idx, svc)
        bg = _qcolor(bg_idx, svc)
        painter.save()
        painter.setOpacity(0.5)
        for dr, dc in cells:
            r, c = row + dr, col + dc
            x, y = self.cell_to_screen(c, r)
            painter.fillRect(x, y, cw, ch, bg)
            painter.setPen(QPen(QColor("#aaaaaa"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, cw - 1, ch - 1)
        painter.setOpacity(1.0)
        if cell_ch and cell_ch not in _EMPTY_CHARS:
            painter.setPen(fg)
            for dr, dc in cells:
                r, c = row + dr, col + dc
                x, y = self.cell_to_screen(c, r)
                painter.drawText(QRect(x, y, cw, ch), Qt.AlignmentFlag.AlignCenter, cell_ch)
        painter.restore()

    def _paint_cel_guides(self, painter, doc, col, row, cw, ch):
        fi      = doc.current_frame_idx
        bounds_a = _cel_bounds(doc.active_layer, fi)
        target   = _layer_at_cursor(doc, col, row)
        same     = (target is doc.active_layer)

        if same:
            bounds_t = None
            ref      = None
        elif target is None:
            bounds_t = None
            ref      = (0, 0, doc.width - 1, doc.height - 1)
        else:
            bounds_t = _cel_bounds(target, fi)
            ref      = bounds_t if bounds_t else (0, 0, doc.width - 1, doc.height - 1)

        COLOR_A = QColor("#4488ff")
        COLOR_T = QColor("#88aaff")
        COLOR_G = QColor("#4488ff")

        painter.setBrush(Qt.BrushStyle.NoBrush)

        if bounds_a:
            x0, y0 = self.cell_to_screen(bounds_a[0], bounds_a[1])
            x1, y1 = self.cell_to_screen(bounds_a[2] + 1, bounds_a[3] + 1)
            painter.setPen(QPen(COLOR_A, 1))
            painter.drawRect(x0, y0, x1 - x0 - 1, y1 - y0 - 1)

        if bounds_t:
            x0, y0 = self.cell_to_screen(bounds_t[0], bounds_t[1])
            x1, y1 = self.cell_to_screen(bounds_t[2] + 1, bounds_t[3] + 1)
            painter.setPen(QPen(COLOR_T, 1, Qt.PenStyle.DashLine))
            painter.drawRect(x0, y0, x1 - x0 - 1, y1 - y0 - 1)

        if bounds_a and ref is not None:
            self._paint_axis_guides_x(painter, bounds_a, ref, COLOR_G, ch)
            self._paint_axis_guides_y(painter, bounds_a, ref, COLOR_G, cw)

    def _paint_axis_guides_x(self, painter, bounds_a, bounds_r, color, ch):
        a_lo, a_hi = bounds_a[0], bounds_a[2]
        r_lo, r_hi = bounds_r[0], bounds_r[2]
        center_y   = (self.cell_to_screen(0, bounds_a[1])[1] +
                      self.cell_to_screen(0, bounds_a[3] + 1)[1]) // 2
        ref_y0 = self.cell_to_screen(0, bounds_r[1])[1]
        ref_y1 = self.cell_to_screen(0, bounds_r[3] + 1)[1]

        def px_lo(c): return self.cell_to_screen(c, 0)[0]
        def px_hi(c): return self.cell_to_screen(c + 1, 0)[0]

        def guide(x0, x1, dist):
            if dist <= 0 or x0 >= x1:
                return
            painter.setPen(QPen(color, 1))
            painter.drawLine(x0, center_y, x1, center_y)
            self._paint_label(painter, (x0 + x1) // 2, center_y - 12, str(dist))

        def connector(px_x):
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if center_y < ref_y0:
                painter.drawLine(px_x, center_y, px_x, ref_y0)
            elif center_y > ref_y1:
                painter.drawLine(px_x, center_y, px_x, ref_y1)

        overlapping = a_lo <= r_hi and a_hi >= r_lo
        if not overlapping:
            if a_hi < r_lo:
                guide(px_hi(a_hi), px_lo(r_lo), r_lo - a_hi - 1)
                connector(px_lo(r_lo))
            else:
                guide(px_hi(r_hi), px_lo(a_lo), a_lo - r_hi - 1)
                connector(px_hi(r_hi))
        else:
            if a_lo != r_lo:
                guide(px_lo(min(a_lo, r_lo)), px_lo(max(a_lo, r_lo)), abs(a_lo - r_lo))
                connector(px_lo(r_lo))
            if a_hi != r_hi:
                guide(px_hi(min(a_hi, r_hi)), px_hi(max(a_hi, r_hi)), abs(a_hi - r_hi))
                connector(px_hi(r_hi))

    def _paint_axis_guides_y(self, painter, bounds_a, bounds_r, color, cw):
        a_lo, a_hi = bounds_a[1], bounds_a[3]
        r_lo, r_hi = bounds_r[1], bounds_r[3]
        center_x   = (self.cell_to_screen(bounds_a[0], 0)[0] +
                      self.cell_to_screen(bounds_a[2] + 1, 0)[0]) // 2
        ref_x0 = self.cell_to_screen(bounds_r[0], 0)[0]
        ref_x1 = self.cell_to_screen(bounds_r[2] + 1, 0)[0]

        def py_lo(r): return self.cell_to_screen(0, r)[1]
        def py_hi(r): return self.cell_to_screen(0, r + 1)[1]

        def guide(y0, y1, dist):
            if dist <= 0 or y0 >= y1:
                return
            painter.setPen(QPen(color, 1))
            painter.drawLine(center_x, y0, center_x, y1)
            self._paint_label(painter, center_x + 6, (y0 + y1) // 2, str(dist))

        def connector(py_y):
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if center_x < ref_x0:
                painter.drawLine(center_x, py_y, ref_x0, py_y)
            elif center_x > ref_x1:
                painter.drawLine(center_x, py_y, ref_x1, py_y)

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

    def _paint_label(self, painter, cx, cy, text: str):
        f = QFont("Monospace", 8, QFont.Weight.Bold)
        painter.setFont(f)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            painter.setPen(QColor("#000000"))
            painter.drawText(cx + dx, cy + dy, text)
        painter.setPen(QColor("#e8e8e8"))
        painter.drawText(cx, cy, text)
        painter.setFont(self._font)

    # ── Gestión de eventos Qt → lógica de herramientas ────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if self._tool_state != _STANDBY:
            return
        x, y   = int(event.position().x()), int(event.position().y())
        button = self._qt_button(event.button())
        alt    = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)

        if self._space_held or button == 2:
            self._tool_state       = _SCROLLING
            self._scroll_origin    = (x, y)
            self._scroll_view_orig = (int(self._view_col), int(self._view_row))
            return

        if alt:
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = self.app._tools["eyedropper"]

        col, row = self.screen_to_cell(x, y)
        self._tool_state = _DRAWING
        self.app.active_tool.on_start(col, row, button)

    def mouseMoveEvent(self, event: QMouseEvent):
        x, y = int(event.position().x()), int(event.position().y())
        col, row = self.screen_to_cell(x, y)

        if self._tool_state == _DRAWING:
            self.update_cursor(col, row)
            self.app.active_tool.on_drag(col, row)
        elif self._tool_state == _SCROLLING:
            ox, oy = self._scroll_origin
            dx = (x - ox) // self._cell_w
            dy = (y - oy) // self._cell_h
            self.set_view(self._scroll_view_orig[0] - dx,
                          self._scroll_view_orig[1] - dy)
        else:
            self.update_cursor(col, row)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._tool_state == _DRAWING:
            x, y     = int(event.position().x()), int(event.position().y())
            col, row = self.screen_to_cell(x, y)
            button = self._qt_button(event.button())
            self.app.active_tool.on_end(col, row, button)
            if self._saved_tool is not None:
                self.app.active_tool = self._saved_tool
                self._saved_tool     = None
        self._tool_state = _STANDBY

    def leaveEvent(self, event):
        self.clear_cursor_highlight()
        self.setCursor(Qt.CursorShape.BlankCursor)

    def wheelEvent(self, event: QWheelEvent):
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        delta = event.angleDelta().y()
        x, y  = int(event.position().x()), int(event.position().y())
        if ctrl:
            if delta > 0:
                self.app.zoom_in(x, y)
            else:
                self.app.zoom_out(x, y)
        else:
            scroll = -3 if delta > 0 else 3
            self.set_view(self._view_col, self._view_row + scroll)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and self._tool_state == _STANDBY:
            self._space_held = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif event.key() in (Qt.Key.Key_Control,):
            self._ctrl_held = True
            if self._cursor_cell:
                self._cel_guides_pos = self._cursor_cell
                self.update()
        else:
            event.ignore()  # propagar al padre (atajos de app)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            self.setCursor(Qt.CursorShape.BlankCursor)
        elif event.key() in (Qt.Key.Key_Control,):
            self._ctrl_held      = False
            self._cel_guides_pos = None
            self.update()
        else:
            event.ignore()

    @staticmethod
    def _qt_button(btn) -> int:
        from PySide6.QtCore import Qt as _Qt
        if btn == _Qt.MouseButton.LeftButton:   return 1
        if btn == _Qt.MouseButton.MiddleButton: return 2
        if btn == _Qt.MouseButton.RightButton:  return 3
        return 1
