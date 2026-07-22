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

import math

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore    import Qt, QRect, QRectF, QPoint, QTimer, QKeyCombination, QEvent
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QImage,
    QPaintEvent, QMouseEvent, QWheelEvent, QKeyEvent, QKeySequence,
)

import core.log as log
from ui.minimap import MinimapOverlay

_log       = log.get("canvas")   # render_frame, zoom, scroll, overlays
_log_paint = log.get("paint")    # por-paintEvent: dirty rect, celdas
_log_cel   = log.get("cel")      # cel guides: bounds, datos
_log_input = log.get("input")    # eventos de ratón y teclado

# ── Paleta ANSI 16 colores (compatibilidad con core/color_service.py) ─────────
ANSI_COLORS = [
    "#000000", "#aa0000", "#00aa00", "#aa5500",
    "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
]

# QColors pre-construidos — evita miles de allocaciones por frame
_ANSI_QCOLORS: list[QColor] = [QColor(c) for c in ANSI_COLORS]
_SVC_QCOLOR_CACHE: dict[str, QColor] = {}  # hex → QColor para modo 256

# ── Niveles de zoom ────────────────────────────────────────────────────────────
_ZOOM_STEPS    = [6, 8, 10, 12, 14, 16, 18, 20, 24]
_BASE_FONT_IDX = _ZOOM_STEPS.index(14)

# ── Estados de la herramienta ──────────────────────────────────────────────────
_STANDBY   = "standby"
_DRAWING   = "drawing"
_SCROLLING = "scrolling"

# ── Helpers para guías de cel (§7) ────────────────────────────────────────────

_EMPTY_CHARS = (" ", "\x00")

# ── Renderizado geométrico de block elements (U+2580–U+259F) ──────────────────
# Igual que foot/alacritty/wezterm: sin usar el glyph del font, para pixel-perfect
# coverage independiente del tamaño de celda.

_SHADE_CACHE: dict = {}   # (pat, fg_rgb, bg_rgb) → QBrush


def _shade_brush(fg: QColor, bg: QColor, pat: int) -> QBrush:
    """
    Crea (o retorna del caché) un QBrush de textura 2×2 para shades.
    pat: 1=░ (25%), 2=▒ (50% checkerboard), 3=▓ (75%)
    Con setBrushOrigin(0,0) en el painter, el patrón tila sin costuras entre celdas.
    """
    key = (pat, fg.rgb(), bg.rgb())
    b = _SHADE_CACHE.get(key)
    if b is None:
        img = QImage(2, 2, QImage.Format.Format_RGB32)
        f, k = fg.rgb(), bg.rgb()
        if pat == 1:    # ░ 25%: 1 fg en 4
            img.setPixel(0, 0, f); img.setPixel(1, 0, k)
            img.setPixel(0, 1, k); img.setPixel(1, 1, k)
        elif pat == 2:  # ▒ 50%: checkerboard
            img.setPixel(0, 0, f); img.setPixel(1, 0, k)
            img.setPixel(0, 1, k); img.setPixel(1, 1, f)
        else:           # ▓ 75%: 3 fg en 4
            img.setPixel(0, 0, f); img.setPixel(1, 0, f)
            img.setPixel(0, 1, k); img.setPixel(1, 1, f)
        _SHADE_CACHE[key] = b = QBrush(img)
    return b


def _draw_block_element(painter, ch: str, x: int, y: int,
                        cw: int, rh: int, fg: QColor, bg: QColor) -> bool:
    """
    Renderiza geométricamente un Unicode Block Element (U+2580–U+259F).
    El bg ya fue pintado por el loop principal; aquí solo pintamos fg.
    Para shades (░▒▓) usamos texture brush con tiling desde (0,0).
    Retorna True si manejado, False para fallback a drawText.
    """
    o = ord(ch)
    if not (0x2580 <= o <= 0x259F):
        return False

    lw = cw // 2        # ancho mitad izquierda
    rw = cw - lw        # ancho mitad derecha
    th = rh // 2        # alto mitad superior
    bh = rh - th        # alto mitad inferior

    if   o == 0x2580:   # ▀ UPPER HALF BLOCK
        painter.fillRect(x, y, cw, th, fg)
    elif o == 0x2581:   # ▁ LOWER 1/8
        painter.fillRect(x, y + rh - max(1, rh >> 3), cw, max(1, rh >> 3), fg)
    elif o == 0x2582:   # ▂ LOWER 2/8
        h = max(1, rh * 2 >> 3)
        painter.fillRect(x, y + rh - h, cw, h, fg)
    elif o == 0x2583:   # ▃ LOWER 3/8
        h = max(1, rh * 3 >> 3)
        painter.fillRect(x, y + rh - h, cw, h, fg)
    elif o == 0x2584:   # ▄ LOWER HALF BLOCK
        painter.fillRect(x, y + th, cw, bh, fg)
    elif o == 0x2585:   # ▅ LOWER 5/8
        h = max(1, rh * 5 >> 3)
        painter.fillRect(x, y + rh - h, cw, h, fg)
    elif o == 0x2586:   # ▆ LOWER 6/8
        h = max(1, rh * 6 >> 3)
        painter.fillRect(x, y + rh - h, cw, h, fg)
    elif o == 0x2587:   # ▇ LOWER 7/8
        h = max(1, rh * 7 >> 3)
        painter.fillRect(x, y + rh - h, cw, h, fg)
    elif o == 0x2588:   # █ FULL BLOCK
        painter.fillRect(x, y, cw, rh, fg)
    elif o == 0x2589:   # ▉ LEFT 7/8
        painter.fillRect(x, y, max(1, cw * 7 >> 3), rh, fg)
    elif o == 0x258A:   # ▊ LEFT 6/8
        painter.fillRect(x, y, max(1, cw * 6 >> 3), rh, fg)
    elif o == 0x258B:   # ▋ LEFT 5/8
        painter.fillRect(x, y, max(1, cw * 5 >> 3), rh, fg)
    elif o == 0x258C:   # ▌ LEFT HALF BLOCK
        painter.fillRect(x, y, lw, rh, fg)
    elif o == 0x258D:   # ▍ LEFT 3/8
        painter.fillRect(x, y, max(1, cw * 3 >> 3), rh, fg)
    elif o == 0x258E:   # ▎ LEFT 2/8
        painter.fillRect(x, y, max(1, cw * 2 >> 3), rh, fg)
    elif o == 0x258F:   # ▏ LEFT 1/8
        painter.fillRect(x, y, max(1, cw >> 3), rh, fg)
    elif o == 0x2590:   # ▐ RIGHT HALF BLOCK
        painter.fillRect(x + lw, y, rw, rh, fg)
    elif o == 0x2591:   # ░ LIGHT SHADE
        painter.fillRect(x, y, cw, rh, _shade_brush(fg, bg, 1))
    elif o == 0x2592:   # ▒ MEDIUM SHADE
        painter.fillRect(x, y, cw, rh, _shade_brush(fg, bg, 2))
    elif o == 0x2593:   # ▓ DARK SHADE
        painter.fillRect(x, y, cw, rh, _shade_brush(fg, bg, 3))
    elif o == 0x2594:   # ▔ UPPER 1/8
        painter.fillRect(x, y, cw, max(1, rh >> 3), fg)
    elif o == 0x2595:   # ▕ RIGHT 1/8
        w = max(1, cw >> 3)
        painter.fillRect(x + cw - w, y, w, rh, fg)
    elif o == 0x2596:   # ▖ QUADRANT LOWER LEFT
        painter.fillRect(x, y + th, lw, bh, fg)
    elif o == 0x2597:   # ▗ QUADRANT LOWER RIGHT
        painter.fillRect(x + lw, y + th, rw, bh, fg)
    elif o == 0x2598:   # ▘ QUADRANT UPPER LEFT
        painter.fillRect(x, y, lw, th, fg)
    elif o == 0x2599:   # ▙ LOWER LEFT + UPPER LEFT + LOWER RIGHT
        painter.fillRect(x, y, lw, rh, fg)
        painter.fillRect(x + lw, y + th, rw, bh, fg)
    elif o == 0x259A:   # ▚ UPPER LEFT + LOWER RIGHT
        painter.fillRect(x, y, lw, th, fg)
        painter.fillRect(x + lw, y + th, rw, bh, fg)
    elif o == 0x259B:   # ▛ UPPER LEFT + UPPER RIGHT + LOWER LEFT
        painter.fillRect(x, y, cw, th, fg)
        painter.fillRect(x, y + th, lw, bh, fg)
    elif o == 0x259C:   # ▜ UPPER LEFT + UPPER RIGHT + LOWER RIGHT
        painter.fillRect(x, y, cw, th, fg)
        painter.fillRect(x + lw, y + th, rw, bh, fg)
    elif o == 0x259D:   # ▝ QUADRANT UPPER RIGHT
        painter.fillRect(x + lw, y, rw, th, fg)
    elif o == 0x259E:   # ▞ UPPER RIGHT + LOWER LEFT
        painter.fillRect(x + lw, y, rw, th, fg)
        painter.fillRect(x, y + th, lw, bh, fg)
    elif o == 0x259F:   # ▟ LOWER LEFT + LOWER RIGHT + UPPER RIGHT
        painter.fillRect(x + lw, y, rw, th, fg)
        painter.fillRect(x, y + th, cw, bh, fg)

    return True


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
    """Convierte un índice de paleta a QColor (con caché para no crear objetos nuevos)."""
    if svc is not None:
        h = svc.color(idx)
        q = _SVC_QCOLOR_CACHE.get(h)
        if q is None:
            _SVC_QCOLOR_CACHE[h] = q = QColor(h)
        return q
    return _ANSI_QCOLORS[idx] if 0 <= idx < 16 else QColor("#000000")


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
        self.setObjectName("ascii_canvas")

        # ── Zoom ──────────────────────────────────────────────────────────
        self._zoom_idx    = _BASE_FONT_IDX
        self._font_family = "DejaVu Sans Mono"
        self._font        = QFont(self._font_family, _ZOOM_STEPS[_BASE_FONT_IDX])
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setFixedPitch(True)
        self._font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
        self._recalc_cell_size()

        # ── Vista (scroll) ─────────────────────────────────────────────────
        self._view_col    = 0
        self._view_row    = 0
        self._needs_center = True   # centrar en el primer paintEvent real
        self._needs_dpr_init = True # recalcular cell_size con DPR real (post-show)

        # ── Estado de la herramienta activa ────────────────────────────────
        self._tool_state    = _STANDBY
        self._scroll_origin: tuple[int, int] | None = None
        self._scroll_view_orig: tuple[int, int] | None = None
        self._space_held    = False
        self._ctrl_held     = False
        self._picker_held   = False   # tecla de "recoger color" (kb_pick_color) sostenida
        self._saved_tool    = None

        # ── Modo cursor de teclado (dibujo sin ratón) ───────────────────────
        self._kb_cursor: tuple[int, int] | None = None
        self._kb_target   = "fg"   # cuál color editan I/J/K/L
        self._kb_char_row = 0      # fila de 10 activa en el grupo de caracteres actual

        # ── Overlays (toda la info necesaria para paintEvent) ──────────────
        self._cursor_cell:   tuple[int, int] | None = None
        self._cursor_vis     = False
        self._sel_rect:      tuple[int, int, int, int] | None = None
        self._paste_preview: tuple[int, int, int, int] | None = None
        self._brush_cursor:  tuple | None = None   # (col, row, cells, ch, fg, bg)
        self._preview_cells: list | None = None    # [(col, row, ch), ...]
        self._cel_guides_pos: tuple[int, int] | None = None  # col, row bajo cursor

        # ── Caché cel guides ───────────────────────────────────────────────
        # _cel_bounds_a : bounds de la capa activa — se computa UNA VEZ por
        #                 sesión Ctrl (invalida en render_frame/keyPress Ctrl).
        # _cel_guides_key  : (bounds_a, id(target), bounds_t, ref) — clave de
        #                 comparación para detectar si las guías cambiaron.
        # _cel_guides_data : (bounds_a, bounds_t, ref) — lo que _paint_cel_guides
        #                 necesita; se actualiza sólo cuando la clave cambia.
        self._cel_bounds_a    = None
        self._cel_guides_key  = None
        self._cel_guides_data = None

        # ── Caché de celdas compuestas por frame ──────────────────────────
        # _frame_caches[frame_idx] → {(row,col): (ch,fg,bg)} para cada frame visitado.
        # Persiste entre cambios de frame durante la animación; solo se invalida
        # cuando el contenido real cambia (edición) o la estructura de capas cambia.
        # Los datos son resolución-independientes: zoom/font NO los invalida.
        #
        # _composite_cache apunta SIEMPRE a _frame_caches[current_frame_idx].
        # _last_frame_idx distingue "navegación de frame" de "edición de contenido"
        # en render_frame() sin necesidad de parámetros extra desde app.py.
        # _doc_id detecta cambio de documento (new_file/open_file).
        self._frame_caches:   dict[int, dict] = {}
        self._composite_cache: dict            = {}
        self._last_frame_idx:  int             = -1
        self._doc_id:          int             = -1
        self._frame_caches[0] = self._composite_cache

        # ── Minimapa ──────────────────────────────────────────────────────
        # Se asigna desde App.__init__ después de crear MinimapOverlay.
        self.minimap: MinimapOverlay | None = None

        # ── Foco y tamaño ─────────────────────────────────────────────────
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setStyleSheet("background-color: #000000;")

        # Rerender al cambiar modo de color
        app.bus.on("color_mode_changed", lambda _: self.update())
        # Cambio de estructura de capas → invalida caches de TODOS los frames
        app.bus.on("layers_changed", lambda _: self.invalidate_all_frames())

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
        fm   = QFontMetrics(self._font)
        dpr  = self.devicePixelRatioF()
        raw_w = fm.horizontalAdvance("X")
        raw_h = fm.lineSpacing()
        if dpr > 1.0:
            # Redondear al siguiente entero cuyo múltiplo con dpr sea entero.
            # Evita que celdas adyacentes dejen 1 device-pixel sin cubrir
            # cuando el compositor Wayland escala el buffer del app.
            self._cell_w = int(math.ceil(math.ceil(raw_w * dpr) / dpr))
            self._cell_h = int(math.ceil(math.ceil(raw_h * dpr) / dpr))
        else:
            self._cell_w = raw_w
            self._cell_h = raw_h
        self._fm_ascent = fm.ascent()
        _log_paint.info(
            f"recalc_cell  dpr={dpr:.4f}"
            f"  font={self._font.pointSize()}pt"
            f"  raw=({raw_w},{raw_h})"
            f"  aligned=({self._cell_w},{self._cell_h})"
            f"  dev_check=({self._cell_w*dpr:.2f},{self._cell_h*dpr:.2f})"
        )

    def screen_to_cell(self, sx: int, sy: int) -> tuple[int, int]:
        return (int(sx) // self._cell_w + self._view_col,
                int(sy) // self._cell_h + self._view_row)

    def cell_to_screen(self, col: int, row: int) -> tuple[int, int]:
        return (col - self._view_col) * self._cell_w, (row - self._view_row) * self._cell_h

    # ── Zoom ──────────────────────────────────────────────────────────────

    def set_font_family(self, name: str):
        """Cambia la familia de fuente del canvas y fuerza redibujado."""
        self._font_family = name
        self._needs_dpr_init = True
        self._apply_zoom()
        self.update()

    def _apply_zoom(self):
        size = _ZOOM_STEPS[self._zoom_idx]
        self._font = QFont(self._font_family, size)
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setFixedPitch(True)
        self._font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
        self._recalc_cell_size()
        pct = int(size / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)
        cw, rh = self._cell_w, self._cell_h
        _log.info(f"zoom  {pct}%  font={size}pt  cell={cw}×{rh}px  family={self._font_family}")
        if hasattr(self.app, "context_bar"):
            self.app.context_bar.set_zoom(pct)
        if hasattr(self.app, "statusbar"):
            self.app.statusbar.set_zoom(size, cw, rh)
        return pct

    def zoom_in(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx < len(_ZOOM_STEPS) - 1:
            self._zoom_anchored(self._zoom_idx + 1, mouse_x, mouse_y)
        pct = int(_ZOOM_STEPS[self._zoom_idx] / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)
        _log.debug(f"zoom_in  → {pct}%  cell={self._cell_w}×{self._cell_h}")
        return pct

    def zoom_out(self, mouse_x=None, mouse_y=None):
        if self._zoom_idx > 0:
            self._zoom_anchored(self._zoom_idx - 1, mouse_x, mouse_y)
        pct = int(_ZOOM_STEPS[self._zoom_idx] / _ZOOM_STEPS[_BASE_FONT_IDX] * 100)
        _log.debug(f"zoom_out  → {pct}%  cell={self._cell_w}×{self._cell_h}")
        return pct

    def zoom_reset(self):
        self._zoom_idx = _BASE_FONT_IDX
        self._apply_zoom()
        self.update()
        _log.debug("zoom_reset  → 100%")
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

    def center_view(self):
        """Alinea el centro del doc con el centro del widget."""
        doc    = self.app.doc
        doc_cx = (doc.width  * self._cell_w) // 2
        doc_cy = (doc.height * self._cell_h) // 2
        wgt_cx = self.width()  // 2
        wgt_cy = self.height() // 2
        self._view_col    = (doc_cx - wgt_cx) // self._cell_w
        self._view_row    = (doc_cy - wgt_cy) // self._cell_h
        self._needs_center = False
        self.update()

    def render_frame(self, _frame=None):
        doc     = self.app.doc
        new_idx = doc.current_frame_idx
        doc_id  = id(doc)

        # ── Detectar cambio de documento (new_file / open_file) ───────────
        if doc_id != self._doc_id:
            self._frame_caches.clear()
            self._doc_id         = doc_id
            self._last_frame_idx = -1

        old_idx = self._last_frame_idx

        if old_idx < 0 or new_idx != old_idx:
            # Navegación de frame (animación / teclas de frame):
            # — guarda el caché parcial del frame anterior
            # — carga el del nuevo frame (o vacío si es la primera visita)
            if old_idx >= 0 and self._composite_cache:
                self._frame_caches[old_idx] = self._composite_cache
            cached = self._frame_caches.get(new_idx)
            if cached is None:
                cached = {}
                self._frame_caches[new_idx] = cached
            self._composite_cache = cached
            _log.debug(
                f"render_frame  nav  {old_idx}→{new_idx}"
                f"  cache_hit={bool(cached)}"
                f"  frames_cached={len(self._frame_caches)}"
            )
        else:
            # Edición de contenido (dibujar, pegar, undo, …):
            # — invalida solo el frame actual
            self._frame_caches.pop(new_idx, None)
            self._composite_cache = {}
            self._frame_caches[new_idx] = self._composite_cache
            _log.debug(f"render_frame  edit  frame={new_idx}")

        self._last_frame_idx  = new_idx
        self._cel_bounds_a    = None
        self._cel_guides_key  = None
        self._cel_guides_data = None
        if self.minimap:
            self.minimap.invalidate()
        self.update()

    def invalidate_all_frames(self):
        """Invalida el caché de todos los frames (cambio de estructura de capas).
        No llama update() — el llamante (render_frame o similares) lo hace."""
        self._frame_caches.clear()
        self._composite_cache = {}
        cur = self.app.doc.current_frame_idx
        self._frame_caches[cur] = self._composite_cache
        self._last_frame_idx = cur
        _log.debug("invalidate_all_frames  (layers_changed)")

    def update_cell(self, col, row, _ch=None, _fg=None, _bg=None):
        # Invalida la celda en el caché y repinta solo esa región. Los valores
        # _ch/_fg/_bg de la herramienta activa se IGNORAN: la celda se recompone
        # vía doc.composite_cell() en paintEvent, de modo que dibujar en una capa
        # inferior o borrar (space + bg=0) respeta siempre la fusión entre capas.
        self._composite_cache.pop((row, col), None)
        sx, sy = self.cell_to_screen(col, row)
        self.update(QRect(sx, sy, self._cell_w, self._cell_h))

    def set_view(self, col: int, row: int):
        doc = self.app.doc
        new_col = int(min(col, max(0, doc.width  - 1)))
        new_row = int(min(row, max(0, doc.height - 1)))
        dx = (int(self._view_col) - new_col) * self._cell_w
        dy = (int(self._view_row) - new_row) * self._cell_h
        self._view_col = new_col
        self._view_row = new_row
        if dx or dy:
            if self.minimap and self.minimap.visible:
                # scroll() desplazaría también los píxeles del minimapa (dibujado
                # en una esquina fija dentro del paintEvent), dejando fantasmas
                # arrastrados por el lienzo. Con el minimapa visible repintamos
                # el widget completo para evitar el smearing.
                self.update()
            else:
                # QWidget.scroll() desplaza los píxeles del backing store y marca
                # como dirty SOLO la franja recién expuesta (no todo el widget).
                # paintEvent recibe event.rect() = esa franja → el cell loop
                # procesa ~42 celdas en vez de ~5000. Las overlays (borde, cursor)
                # se pintan sin clipping y cubren el widget completo.
                self.scroll(dx, dy)

    # ── Overlays — setters que disparan update() ──────────────────────────

    def _overlay_rect(self) -> QRect:
        """Rect en pantalla que ocupa el overlay de cursor/pincel en el estado actual."""
        r = QRect()
        if self._cursor_vis and self._cursor_cell:
            x, y = self.cell_to_screen(*self._cursor_cell)
            r = r.united(QRect(x, y, self._cell_w, self._cell_h))
        if self._brush_cursor:
            c0, r0, cells = self._brush_cursor[0], self._brush_cursor[1], self._brush_cursor[2]
            for dr, dc in cells:
                x, y = self.cell_to_screen(c0 + dc, r0 + dr)
                r = r.united(QRect(x, y, self._cell_w, self._cell_h))
        return r

    def update_cursor(self, col: int, row: int):
        """Actualiza el cursor y los overlays dinámicos. Recibe col/row directamente."""
        doc = self.app.doc
        if not (0 <= col < doc.width and 0 <= row < doc.height):
            self.clear_cursor_highlight()
            if hasattr(self.app, "statusbar"):
                self.app.statusbar.set_pos(None, None)
            return

        # Dirty rect del estado ANTERIOR (para borrar overlay viejo)
        old_dirty = self._overlay_rect()

        self._cursor_cell = (col, row)
        is_brush = getattr(self.app.active_tool, "context_key", None) == "brush"

        if is_brush:
            brush = self.app.active_brush
            self._brush_cursor = (col, row, brush.footprint,
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

        has_paste = (self.app.clipboard is not None
                     and self.app.active_tool.name == "selection")
        if has_paste:
            n_rows = len(self.app.clipboard)
            n_cols = len(self.app.clipboard[0]) if n_rows else 0
            self._paste_preview = (col, row, n_rows, n_cols)
        else:
            self._paste_preview = None

        if has_paste:
            # El paste preview puede cubrir una zona grande → repintado completo
            self.update()
        elif self._ctrl_held:
            self._update_cel_guides(doc, col, row, old_dirty)
        else:
            combined = old_dirty.united(self._overlay_rect())
            self.update(combined if combined.isValid() else QRect())

    def clear_cursor_highlight(self):
        dirty = self._overlay_rect()
        self._cursor_cell    = None
        self._cursor_vis     = False
        self._brush_cursor   = None
        self._cel_guides_pos = None
        if dirty.isValid():
            self.update(dirty)
        else:
            self.update()

    def _update_cel_guides(self, doc, col, row, _old_dirty: QRect):
        """Actualiza _cel_guides_data de forma perezosa y fuerza repintado completo.

        La optimización aquí es SOLO de cómputo: _cel_bounds_a se calcula una
        vez por sesión Ctrl; bounds_t y ref solo cuando cambia el target layer.
        El repintado es siempre completo porque las líneas de medición abarcan
        todo el canvas y Wayland no garantiza preservar el buffer fuera del rect
        sucio cuando se hace un update parcial.
        """
        # bounds_a: una sola vez por sesión Ctrl (o tras render_frame)
        if self._cel_bounds_a is None:
            self._cel_bounds_a = _cel_bounds(doc.active_layer, doc.current_frame_idx)
            _log_cel.debug(f"cel_guides  bounds_a calculados: {self._cel_bounds_a}  layer='{doc.active_layer.name}'")
        bounds_a = self._cel_bounds_a

        # target layer: O(capas), siempre rápido
        target    = _layer_at_cursor(doc, col, row)
        target_id = id(target)

        new_key = (bounds_a, target_id)
        if self._cel_guides_key is None or self._cel_guides_key[:2] != new_key:
            # Target cambió: recomputa bounds_t (solo en este caso)
            same = (target is doc.active_layer)
            if same:
                bounds_t, ref = None, None
                _log_cel.debug(f"cel_guides  ({col},{row})  same=True → sin mediciones")
            elif target is None:
                bounds_t = None
                ref      = (0, 0, doc.width - 1, doc.height - 1)
                _log_cel.debug(f"cel_guides  ({col},{row})  target=None  bounds_a={bounds_a}  ref={ref}")
            else:
                fi       = doc.current_frame_idx
                bounds_t = _cel_bounds(target, fi)
                ref      = bounds_t if bounds_t else (0, 0, doc.width - 1, doc.height - 1)
                _log_cel.debug(f"cel_guides  ({col},{row})  target='{target.name}'  bounds_t={bounds_t}  ref={ref}")

            self._cel_guides_key  = (bounds_a, target_id, bounds_t, ref)
            self._cel_guides_data = (bounds_a, bounds_t, ref)

        self.update()   # siempre completo: las guías abarcan todo el canvas

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
        # Primera pasada: re-calcular tamaño de celda con el DPR real del display
        # (en __init__ el widget aún no tiene pantalla y devicePixelRatioF() puede
        # devolver 1.0 aunque sea un display HiDPI o con fractional scaling).
        if self._needs_dpr_init:
            self._needs_dpr_init = False
            self._recalc_cell_size()
            scr      = self.screen()
            scr_name = scr.name() if scr else "?"
            scr_dpr  = scr.devicePixelRatio() if scr else 0.0
            _log_paint.info(
                f"dpr_init"
                f"  widget={self.devicePixelRatioF():.4f}"
                f"  window={self.window().devicePixelRatioF():.4f}"
                f"  screen={scr_name}  screen_dpr={scr_dpr:.4f}"
            )

        # paintEvent garantiza tamaño real: centrar aquí la primera vez.
        if self._needs_center:
            self.center_view()   # pone _needs_center=False y llama update()
            return               # abortar este frame; el update() repintará centrado

        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setFont(self._font)
        # Brush origin en (0,0) del widget — los shade brushes (░▒▓) usan tiling
        # absoluto para que celdas adyacentes del mismo shade sean seamless.
        painter.setBrushOrigin(0, 0)

        doc  = self.app.doc
        svc  = self.app.color_service
        show_grid = getattr(self.app, "_show_grid", False)

        cw, rh = self._cell_w, self._cell_h   # ancho y alto de celda

        # ── Fondo del área exterior al documento ──────────────────────────
        # Pinta el rect sucio completo con el color de fondo del canvas antes
        # de dibujar celdas, para que el área fuera del documento sea visible.
        ts = getattr(self.app, "theme_service", None)
        cbg_hex = ts.canvas_bg_color() if ts else ""
        if cbg_hex:
            painter.fillRect(event.rect(), QColor(cbg_hex))
        else:
            painter.fillRect(event.rect(), self.palette().color(
                self.backgroundRole()))

        # ── Celdas — sólo las que caen dentro del rect sucio ──────────────
        vc_off = int(self._view_col)
        vr_off = int(self._view_row)
        dirty  = event.rect()

        col_lo = max(0,          dirty.left()   // cw + vc_off)
        col_hi = min(doc.width,  dirty.right()  // cw + vc_off + 2)
        row_lo = max(0,          dirty.top()    // rh + vr_off)
        row_hi = min(doc.height, dirty.bottom() // rh + vr_off + 2)
        _log_paint.debug(
            f"paint  dpr={self.devicePixelRatioF():.2f}"
            f"  cw={cw}  rh={rh}"
            f"  dirty={dirty.width()}×{dirty.height()}@({dirty.x()},{dirty.y()})"
            f"  cols={col_lo}:{col_hi}  rows={row_lo}:{row_hi}"
        )

        # _composite_cache apunta al dict del frame actual en _frame_caches.
        # Se construye lazily (solo celdas visibles); persiste entre repaints
        # del mismo frame y entre visitas de animación al mismo frame.
        cache = self._composite_cache

        _last_fg = None
        for drow in range(row_lo, row_hi):
            vr = drow - vr_off
            y_row = vr * rh
            painter.setClipRect(0, y_row, self.width(), rh)
            for dcol in range(col_lo, col_hi):
                vc = dcol - vc_off
                key = (drow, dcol)
                if key not in cache:
                    cache[key] = doc.composite_cell(dcol, drow)
                cell_ch, fg_idx, bg_idx = cache[key]
                x = vc * cw
                bg_qc = _qcolor(bg_idx, svc)
                painter.fillRect(x, y_row, cw + 1, rh + 1, bg_qc)
                if cell_ch and cell_ch not in _EMPTY_CHARS:
                    fg_qc = _qcolor(fg_idx, svc)
                    if not _draw_block_element(painter, cell_ch, x, y_row, cw, rh, fg_qc, bg_qc):
                        if fg_idx != _last_fg:
                            painter.setPen(fg_qc)
                            _last_fg = fg_idx
                        painter.drawText(QRect(x, y_row, cw, rh), Qt.AlignmentFlag.AlignCenter, cell_ch)
        painter.setClipping(False)

        # ── Borde del documento ───────────────────────────────────────────
        self._paint_doc_border(painter, doc, cw, rh)

        # ── Rejilla opcional ──────────────────────────────────────────────
        if show_grid:
            self._paint_grid(painter, doc, cw, rh)

        # ── Preview (rubber-band de herramientas de forma) ─────────────────
        if self._preview_cells:
            painter.setPen(QColor("#00FF88"))
            for p_col, p_row, p_ch in self._preview_cells:
                x, y = self.cell_to_screen(p_col, p_row)
                painter.drawText(QRect(x, y, cw, rh), Qt.AlignmentFlag.AlignCenter, p_ch)

        # ── Guías de cel (Ctrl) ────────────────────────────────────────────
        if self._ctrl_held and self._cel_guides_data:
            self._paint_cel_guides(painter, cw, rh)

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
            self._paint_brush_cursor(painter, svc, cw, rh)

        # ── Minimapa ──────────────────────────────────────────────────────
        if self.minimap:
            self.minimap.paint(painter, self, doc, svc)

        # ── Cursor de celda ───────────────────────────────────────────────
        if self._cursor_vis and self._cursor_cell:
            col, row = self._cursor_cell
            x, y = self.cell_to_screen(col, row)
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, cw - 1, rh - 1)

        # ── Cursor de teclado (modo dibujo sin ratón) ───────────────────────
        if self.app._kb_draw_mode and self._kb_cursor:
            col, row = self._kb_cursor
            x, y = self.cell_to_screen(col, row)
            color = "#00FFFF" if self._kb_target == "fg" else "#FFAA00"
            painter.setPen(QPen(QColor(color), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x + 1, y + 1, cw - 3, rh - 3)

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

    def _paint_cel_guides(self, painter, cw, ch):
        """Pinta guías de cel usando datos pre-calculados en _cel_guides_data."""
        if not self._cel_guides_data:
            return
        bounds_a, bounds_t, ref = self._cel_guides_data

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
            # Centrar la etiqueta en la porción visible (x0 puede ser negativo
            # cuando el canvas está desplazado — el punto medio teórico quedaría
            # fuera de pantalla).
            vis_x0 = max(x0, 0)
            vis_x1 = min(x1, self.width())
            if vis_x1 > vis_x0:
                self._paint_label(painter, (vis_x0 + vis_x1) // 2, center_y - 12, f"{dist}c")

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
            # Ídem: centrar en la porción visible cuando y0 es negativo por scroll.
            vis_y0 = max(y0, 0)
            vis_y1 = min(y1, self.height())
            if vis_y1 > vis_y0:
                self._paint_label(painter, center_x + 6, (vis_y0 + vis_y1) // 2, f"{dist}c")

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
            _log_input.debug(f"mouse_press  scroll_start  ({x},{y})")
            return

        # Clic derecho = borrar; alt o la tecla de "recoger color" (F por
        # defecto, misma acción que en el modo cursor de teclado) = cuentagotas
        # directo. Se sustituye temporalmente la herramienta activa — mouseReleaseEvent
        # la restaura.
        if button == 3:
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = self.app._tools["eraser"]
        elif alt or self._picker_held:
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = self.app._tools["eyedropper"]

        col, row = self.screen_to_cell(x, y)
        _log_input.debug(f"mouse_press  btn={button}  ({x},{y}) → cell({col},{row})  tool={self.app.active_tool.name}")
        self._tool_state = _DRAWING
        self.app.active_tool.on_start(col, row, 1)

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
            return  # SizeAllCursor ya está activo; no sobreescribir
        else:
            self.update_cursor(col, row)

        # Cursor del sistema: cruceta fuera del área del documento, invisible dentro
        # (el canvas dibuja su propio indicador de celda sobre el documento)
        if not self._space_held:
            doc   = self.app.doc
            shape = (Qt.CursorShape.BlankCursor
                     if 0 <= col < doc.width and 0 <= row < doc.height
                     else Qt.CursorShape.CrossCursor)
            if self.cursor().shape() != shape:
                self.setCursor(shape)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._tool_state == _DRAWING:
            x, y     = int(event.position().x()), int(event.position().y())
            col, row = self.screen_to_cell(x, y)
            _log_input.debug(f"mouse_release  btn={self._qt_button(event.button())}  cell({col},{row})")
            self.app.active_tool.on_end(col, row, 1)
            if self.minimap:
                self.minimap.invalidate()
                self.update()   # repintado completo: el dirty de on_end puede excluir el minimap
            if self._saved_tool is not None:
                self.app.active_tool = self._saved_tool
                self._saved_tool     = None
        self._tool_state = _STANDBY

    def leaveEvent(self, event):
        self.clear_cursor_highlight()
        self.setCursor(Qt.CursorShape.BlankCursor)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.app.swap_colors()
            return
        ctrl  = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        dy = event.angleDelta().y()
        dx = event.angleDelta().x()   # rueda horizontal nativa (trackpad) o gesto lateral
        x, y = int(event.position().x()), int(event.position().y())
        if ctrl:
            if dy > 0:
                self.app.zoom_in(x, y)
            else:
                self.app.zoom_out(x, y)
        elif shift or dx:
            delta  = dx if dx else dy
            scroll = -3 if delta > 0 else 3
            self.set_view(self._view_col + scroll, self._view_row)
        else:
            scroll = -3 if dy > 0 else 3
            self.set_view(self._view_col, self._view_row + scroll)

    def event(self, ev):
        # Qt intercepta Tab/Backtab para navegación de foco ANTES de que
        # lleguen a keyPressEvent (QWidget::event los redirige a
        # focusNextPrevChild). El toggle del modo cursor de teclado usa Tab
        # por defecto, así que hay que capturarlo aquí explícitamente.
        if ev.type() == QEvent.Type.KeyPress and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.keyPressEvent(ev)
            return True
        return super().event(ev)

    def keyPressEvent(self, event: QKeyEvent):
        if self._matches_action("kb_draw_toggle", event):
            turning_on = not self.app._kb_draw_mode
            _log_input.debug(f"kb_draw_toggle  → {'ON' if turning_on else 'OFF'}")
            self.app.set_kb_draw_mode(turning_on)
            if turning_on:
                self._clamp_kb_cursor()
                self.app.char_panel.set_kb_row_indicator(self._kb_char_row)
            else:
                self.app.char_panel.set_kb_row_indicator(None)
            self.update()
            return

        if self.app._kb_draw_mode:
            if event.key() == Qt.Key.Key_Escape:
                _log_input.debug("kb_draw  Escape → OFF")
                self.app.set_kb_draw_mode(False)
                self.app.char_panel.set_kb_row_indicator(None)
                self.update()
                return
            if self._handle_kb_draw_key(event):
                return
            event.ignore()
            return

        if event.key() == Qt.Key.Key_Space and self._tool_state == _STANDBY:
            self._space_held = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            _log_input.debug("key_press  Space → scroll mode")
        elif event.key() in (Qt.Key.Key_Control,):
            self._ctrl_held       = True
            self._cel_bounds_a    = None   # recomputa para la capa activa actual
            self._cel_guides_key  = None
            self._cel_guides_data = None
            _log_input.debug(f"key_press  Ctrl → cel guides  cursor={self._cursor_cell}")
            if self._cursor_cell:
                col, row = self._cursor_cell
                self._cel_guides_pos = (col, row)
                self._update_cel_guides(self.app.doc, col, row, QRect())
        elif self._matches_action("kb_pick_color", event):
            self._picker_held = True
            _log_input.debug("key_press  pick_color-hold ON (modo ratón)")
        else:
            event.ignore()  # propagar al padre (atajos de app)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            self.setCursor(Qt.CursorShape.BlankCursor)
        elif event.key() in (Qt.Key.Key_Control,):
            self._ctrl_held       = False
            self._cel_guides_pos  = None
            self._cel_guides_data = None
            self._cel_guides_key  = None
            _log_input.debug("key_release  Ctrl → cel guides off")
            self.update()
        elif self._matches_action("kb_pick_color", event):
            self._picker_held = False
            _log_input.debug("key_release  pick_color-hold OFF (modo ratón)")
        else:
            event.ignore()

    # ── Modo cursor de teclado (dibujo sin ratón) ───────────────────────────

    def _matches_action(self, action_id: str, event: QKeyEvent) -> bool:
        combo = QKeyCombination(event.modifiers(), Qt.Key(event.key()))
        text  = QKeySequence(combo).toString(QKeySequence.SequenceFormat.PortableText)
        return bool(text) and text in self.app.shortcut_mgr.keys(action_id)

    def _handle_kb_draw_key(self, event: QKeyEvent) -> bool:
        """Interpreta una tecla mientras el modo cursor está activo.
        Devuelve True si la consumió (no debe propagarse)."""
        doc = self.app.doc
        if self._kb_cursor is None:
            self._clamp_kb_cursor()
        col, row = self._kb_cursor
        _log_input.debug(f"kb_draw  key={event.text()!r}  cursor=({col},{row})  target={self._kb_target}")

        if self._matches_action("kb_cursor_up", event):
            row = max(0, row - 1)
        elif self._matches_action("kb_cursor_down", event):
            row = min(doc.height - 1, row + 1)
        elif self._matches_action("kb_cursor_left", event):
            col = max(0, col - 1)
        elif self._matches_action("kb_cursor_right", event):
            col = min(doc.width - 1, col + 1)
        elif self._matches_action("kb_pan_up", event):
            self.set_view(self._view_col, self._view_row - 1)
            return True
        elif self._matches_action("kb_pan_down", event):
            self.set_view(self._view_col, self._view_row + 1)
            return True
        elif self._matches_action("kb_pan_left", event):
            self.set_view(self._view_col - 1, self._view_row)
            return True
        elif self._matches_action("kb_pan_right", event):
            self.set_view(self._view_col + 1, self._view_row)
            return True
        elif self._matches_action("kb_execute", event):
            _log_input.debug(f"kb_draw  execute tool={self.app.active_tool.name}  ({col},{row})")
            self._kb_run_tool(col, row)
            return True
        elif self._matches_action("kb_erase", event):
            _log_input.debug(f"kb_draw  erase  ({col},{row})")
            self._erase_at(col, row)
            return True
        elif self._matches_action("kb_toggle_fgbg", event):
            self._kb_target = "bg" if self._kb_target == "fg" else "fg"
            _log_input.debug(f"kb_draw  toggle_fgbg  → {self._kb_target}")
            self.app.statusbar.showMessage(
                f"Editando color de {'fondo' if self._kb_target == 'bg' else 'frente'}", 1500)
            self.update()
            return True
        elif self._matches_action("kb_pick_color", event):
            _log_input.debug(f"kb_draw  pick_color  ({col},{row})")
            self.app._tools["eyedropper"].on_start(col, row, 1)
            return True
        elif self._matches_action("kb_color_up", event):
            self._kb_cycle_color(-1, axis="row")
            return True
        elif self._matches_action("kb_color_down", event):
            self._kb_cycle_color(+1, axis="row")
            return True
        elif self._matches_action("kb_color_left", event):
            self._kb_cycle_color(-1, axis="col")
            return True
        elif self._matches_action("kb_color_right", event):
            self._kb_cycle_color(+1, axis="col")
            return True
        elif self._matches_action("kb_char_row_up", event):
            self._kb_char_row = max(0, self._kb_char_row - 1)
            self.app.char_panel.set_kb_row_indicator(self._kb_char_row)
            _log_input.debug(f"kb_draw  char_row → {self._kb_char_row}")
            self.update()
            return True
        elif self._matches_action("kb_char_row_down", event):
            panel   = self.app.char_panel
            n_chars = len(panel.group_chars(panel.current_group_index()))
            max_row = max(0, (n_chars - 1) // 10)
            self._kb_char_row = min(max_row, self._kb_char_row + 1)
            panel.set_kb_row_indicator(self._kb_char_row)
            _log_input.debug(f"kb_draw  char_row → {self._kb_char_row}")
            self.update()
            return True
        elif self._matches_action("kb_char_group_prev", event):
            panel = self.app.char_panel
            n     = len(panel.group_names())
            panel.select_group((panel.current_group_index() - 1) % n)
            self._kb_char_row = 0
            panel.set_kb_row_indicator(self._kb_char_row)
            _log_input.debug(f"kb_draw  char_group → {panel.current_group_index()}")
            self.update()
            return True
        elif self._matches_action("kb_char_group_next", event):
            panel = self.app.char_panel
            n     = len(panel.group_names())
            panel.select_group((panel.current_group_index() + 1) % n)
            self._kb_char_row = 0
            panel.set_kb_row_indicator(self._kb_char_row)
            _log_input.debug(f"kb_draw  char_group → {panel.current_group_index()}")
            self.update()
            return True
        elif (Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9
              and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            slot = 9 if event.key() == Qt.Key.Key_0 else event.key() - Qt.Key.Key_1
            ok   = self.app.char_panel.pick_slot(self._kb_char_row, slot)
            _log_input.debug(f"kb_draw  pick_char  row={self._kb_char_row}  slot={slot}  ok={ok}")
            return True
        else:
            _log_input.debug(f"kb_draw  key sin acción asignada: {event.text()!r}")
            return False

        self._kb_cursor = (col, row)
        self._ensure_kb_cursor_visible()
        self.update()
        return True

    def _clamp_kb_cursor(self):
        """Ancla/reancla el cursor de teclado dentro de los límites del documento.
        _view_col/_view_row pueden ser negativos (lienzo centrado si es más
        chico que el viewport), así que no sirven como posición sin recortar."""
        doc = self.app.doc
        col, row = self._kb_cursor if self._kb_cursor is not None else (self._view_col, self._view_row)
        col = max(0, min(int(col), doc.width  - 1))
        row = max(0, min(int(row), doc.height - 1))
        self._kb_cursor = (col, row)

    def _kb_run_tool(self, col: int, row: int):
        """Ejecuta la herramienta activa en una sola celda (equivale a clic sin arrastre)."""
        tool = self.app.active_tool
        tool.on_start(col, row, 1)
        tool.on_end(col, row, 1)
        if self.minimap:
            self.minimap.invalidate()
        self.update()

    def _erase_at(self, col: int, row: int):
        """Borra una celda con la herramienta borrador, sin cambiar la activa (como el clic derecho)."""
        saved = self.app.active_tool
        self.app.active_tool = self.app._tools["eraser"]
        self.app.active_tool.on_start(col, row, 1)
        self.app.active_tool.on_end(col, row, 1)
        self.app.active_tool = saved
        if self.minimap:
            self.minimap.invalidate()
        self.update()

    def _kb_cycle_color(self, direction: int, axis: str):
        """Navega la paleta activa; el color bajo el cursor se aplica de inmediato
        (fg o bg según _kb_target). axis='row' salta de fila (I/K), 'col' de
        columna (J/L) — misma grilla que ColorPanel."""
        from core.color_service import palette_cols
        svc   = self.app.color_service
        count = svc.count()
        step  = palette_cols(svc.mode) if axis == "row" else 1
        current = self.app.fg_color if self._kb_target == "fg" else self.app.bg_color
        new_idx = (current + direction * step) % count
        _log_input.debug(f"kb_draw  color {self._kb_target}  {current} → {new_idx}  (axis={axis})")
        if self._kb_target == "fg":
            self.app.set_fg_color(new_idx)
        else:
            self.app.set_bg_color(new_idx)

    def _ensure_kb_cursor_visible(self):
        """Desplaza la vista lo mínimo necesario para mantener el cursor de teclado visible."""
        col, row = self._kb_cursor
        vis_c = max(1, self.width()  // self._cell_w)
        vis_r = max(1, self.height() // self._cell_h)
        new_col, new_row = self._view_col, self._view_row
        if col < self._view_col:
            new_col = col
        elif col >= self._view_col + vis_c:
            new_col = col - vis_c + 1
        if row < self._view_row:
            new_row = row
        elif row >= self._view_row + vis_r:
            new_row = row - vis_r + 1
        if (new_col, new_row) != (self._view_col, self._view_row):
            self.set_view(new_col, new_row)

    @staticmethod
    def _qt_button(btn) -> int:
        from PySide6.QtCore import Qt as _Qt
        if btn == _Qt.MouseButton.LeftButton:   return 1
        if btn == _Qt.MouseButton.MiddleButton: return 2
        if btn == _Qt.MouseButton.RightButton:  return 3
        return 1
