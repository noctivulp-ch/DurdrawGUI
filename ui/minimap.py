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

        # Indicador de viewport en coords de imagen.
        # Se calculan las dos ESQUINAS y se clampean individualmente — esto
        # maneja correctamente view_col/row negativos (doc más pequeño que la
        # vista, o centrado) y desbordamientos por abajo/derecha.
        scale_x = img_w / doc.width
        scale_y = img_h / doc.height
        vc      = canvas._view_col
        vr      = canvas._view_row
        vis_c   = max(1, canvas.width()  // canvas._cell_w)
        vis_r   = max(1, canvas.height() // canvas._cell_h)

        x0 = ix + int(vc           * scale_x)
        y0 = iy + int(vr           * scale_y)
        x1 = ix + int((vc + vis_c) * scale_x)
        y1 = iy + int((vr + vis_r) * scale_y)

        x0 = max(ix, min(x0, ix + img_w))
        y0 = max(iy, min(y0, iy + img_h))
        x1 = max(ix, min(x1, ix + img_w))
        y1 = max(iy, min(y1, iy + img_h))

        if x1 > x0 and y1 > y0:
            painter.setPen(QPen(QColor(_VP_CLR), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)

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

        # Composición una sola vez (O(w·h)) en lugar de composite_cell por píxel
        # (O(w'·h'·capas)) — sobre 240×67 baja el rebuild de ~40 ms a pocos ms.
        comp    = doc.composite_frame()
        content = comp.content
        cmap    = comp.newColorMap

        # Paleta pre-resuelta a int RGB: setPixel(int) evita construir un QColor
        # por píxel (el otro cuello de botella del bucle en Python).
        n_pal = svc.count() if svc is not None else 16
        pal   = [_qcolor(i, svc).rgb() for i in range(n_pal)]

        def rgb(idx):
            return pal[idx % n_pal]

        image = QImage(img_w, img_h, QImage.Format.Format_RGB32)

        for py in range(img_h):
            row = min(int(py * cells_per_px_y), doc.height - 1)
            crow = content[row]
            mrow = cmap[row]
            for px in range(img_w):
                col = min(int(px * cells_per_px_x), doc.width - 1)
                ch  = crow[col]
                fg_idx, bg_idx = mrow[col]
                if ch and ch not in _EMPTY_CHARS:
                    image.setPixel(px, py, rgb(fg_idx))
                else:
                    image.setPixel(px, py, rgb(bg_idx))

        return image
