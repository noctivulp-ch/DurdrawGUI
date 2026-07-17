"""Overlay de minimapa — preview del lienzo completo en una esquina."""

from __future__ import annotations

from PySide6.QtGui   import QColor, QImage, QPainter, QPen
from PySide6.QtCore  import QRect, Qt

_ANSI_COLORS = [
    "#000000", "#aa0000", "#00aa00", "#aa5500",
    "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
]

_EMPTY_CHARS = (" ", "\x00")
_MARGIN      = 10    # distancia al borde del widget
_PADDING     = 4     # espacio interior alrededor de la imagen
_BORDER_CLR  = "#666666"
_BG_CLR      = "#111111"
_VP_CLR      = "#ffffff"


def _qcolor(idx: int, svc=None) -> QColor:
    if svc is not None:
        return QColor(svc.color(idx))
    return QColor(_ANSI_COLORS[idx] if 0 <= idx < 16 else "#000000")


class MinimapOverlay:
    """Minimapa dibujado al final del paintEvent de AsciiCanvas.

    Desacoplado del lienzo: recibe doc y svc en paint() y no guarda
    referencias a widgets más allá del AppConfig.
    """

    def __init__(self, config):
        self._config = config
        self._image: QImage | None = None

    # ── API pública ────────────────────────────────────────────────────

    @property
    def visible(self) -> bool:
        return bool(self._config.get("minimap_visible"))

    @property
    def corner(self) -> str:
        return str(self._config.get("minimap_corner", "TR"))

    def toggle(self):
        self._config.set("minimap_visible", not self.visible)

    def invalidate(self):
        """Marca la imagen cacheada como obsoleta (llamar tras render_frame)."""
        self._image = None

    def paint(self, painter: QPainter, canvas, doc, svc):
        """Dibuja el minimapa sobre el lienzo si está visible."""
        if not self.visible:
            return

        panel_w = int(self._config.get("minimap_max_w", 240))
        panel_h = int(self._config.get("minimap_max_h", 160))

        if self._image is None:
            self._image = self._rebuild(doc, svc, panel_w, panel_h)

        img_w  = self._image.width()
        img_h  = self._image.height()
        w_w    = canvas.width()
        w_h    = canvas.height()
        corner = self.corner

        # El panel es de tamaño fijo; la imagen se centra dentro de él
        box_w = panel_w + 2 * _PADDING
        box_h = panel_h + 2 * _PADDING

        if corner == "TL":
            bx, by = _MARGIN, _MARGIN
        elif corner == "TR":
            bx, by = w_w - box_w - _MARGIN, _MARGIN
        elif corner == "BL":
            bx, by = _MARGIN, w_h - box_h - _MARGIN
        else:                           # BR por defecto
            bx, by = w_w - box_w - _MARGIN, w_h - box_h - _MARGIN

        # Fondo y borde del panel (tamaño siempre igual)
        painter.fillRect(bx, by, box_w, box_h, QColor(_BG_CLR))
        painter.setPen(QPen(QColor(_BORDER_CLR), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bx, by, box_w - 1, box_h - 1)

        # Imagen centrada dentro del área interior del panel
        panel_ix = bx + _PADDING
        panel_iy = by + _PADDING
        ix = panel_ix + (panel_w - img_w) // 2
        iy = panel_iy + (panel_h - img_h) // 2
        painter.drawImage(ix, iy, self._image)

        # Indicador de viewport en coords de imagen
        scale_x = img_w / doc.width
        scale_y = img_h / doc.height
        cw      = canvas._cell_w
        ch      = canvas._cell_h
        vc      = canvas._view_col
        vr      = canvas._view_row
        vis_c   = max(1, canvas.width()  // cw)
        vis_r   = max(1, canvas.height() // ch)

        vp_x = ix + int(vc * scale_x)
        vp_y = iy + int(vr * scale_y)
        vp_w = max(1, int(vis_c * scale_x))
        vp_h = max(1, int(vis_r * scale_y))

        # Clamp al área de la imagen
        vp_x = max(ix, min(vp_x, ix + img_w - 1))
        vp_y = max(iy, min(vp_y, iy + img_h - 1))
        vp_w = min(vp_w, ix + img_w - vp_x)
        vp_h = min(vp_h, iy + img_h - vp_y)

        painter.setPen(QPen(QColor(_VP_CLR), 1, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(vp_x, vp_y, vp_w - 1, vp_h - 1)

    # ── Construcción de imagen ─────────────────────────────────────────

    def _rebuild(self, doc, svc, panel_w: int, panel_h: int) -> QImage:
        """Escala el lienzo para ajustarse al panel con relación de aspecto 1:2 (col:fila)."""
        # Los caracteres ASCII tienen altura ~2× su ancho: escalar Y en consecuencia.
        visual_h = doc.height * 2
        scale    = min(panel_w / doc.width, panel_h / visual_h)
        img_w    = max(1, round(doc.width   * scale))
        img_h    = max(1, round(visual_h    * scale))

        cells_per_px_x = doc.width  / img_w
        cells_per_px_y = doc.height / img_h   # < cells_per_px_x por el ratio 1:2

        image = QImage(img_w, img_h, QImage.Format.Format_RGB32)

        for py in range(img_h):
            row = min(int(py * cells_per_px_y), doc.height - 1)
            for px in range(img_w):
                col = min(int(px * cells_per_px_x), doc.width - 1)
                ch, fg_idx, bg_idx = doc.composite_cell(col, row)
                if ch and ch not in _EMPTY_CHARS:
                    color = _qcolor(fg_idx, svc)
                else:
                    color = _qcolor(bg_idx, svc)
                image.setPixelColor(px, py, color)

        return image
