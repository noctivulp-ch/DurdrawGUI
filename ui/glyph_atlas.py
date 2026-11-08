"""Atlas de máscaras de glifo para core/raster.rasterize().

Cada carácter se dibuja una sola vez, blanco sobre negro, con el mismo QPainter
y la misma función de dibujo que usaba el lienzo celda a celda. Así el raster
vectorizado da los mismos píxeles (lo comprueba tests/test_raster.py).

Los sombreados ░▒▓ usan una textura 2×2 alineada al origen del widget, así que
su máscara depende de la paridad de la posición de la celda en píxeles: cada
uno tiene 4 máscaras consecutivas, una por fase (px, py) → base + py·2 + px.

Detalle: docs/decisiones/0002-raster-numpy.md.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

SHADES = ("░", "▒", "▓")
_EMPTY = (" ", "\x00", "")
_WHITE = QColor("#ffffff")
_BLACK = QColor("#000000")


class GlyphAtlas:
    def __init__(self, font, cell_w: int, cell_h: int, dpr: float, draw_glyph):
        """draw_glyph(painter, ch, cell_w, cell_h, fg, bg): dibuja un carácter en
        (0, 0) como lo haría el lienzo."""
        self.font = font
        self.cell_w, self.cell_h, self.dpr = cell_w, cell_h, dpr
        self.dev_w = round(cell_w * dpr)
        self.dev_h = round(cell_h * dpr)
        self._draw = draw_glyph
        self.masks = np.zeros((64, self.dev_h, self.dev_w), dtype=np.uint8)
        self.n_masks = 1                      # máscara 0: vacía
        self.lut = np.zeros(0, dtype=np.int32)   # código → máscara base
        self.shade = np.zeros(0, dtype=bool)     # código → es sombreado

    def key(self):
        return (self.font.family(), self.font.pointSize(), self.cell_w, self.cell_h, self.dpr)

    def ensure(self, chars: list[str]):
        """Genera las máscaras que falten para los códigos 0..len(chars)-1."""
        start = len(self.lut)
        if start >= len(chars):
            return
        new_lut = np.zeros(len(chars), dtype=np.int32)
        new_shade = np.zeros(len(chars), dtype=bool)
        new_lut[:start] = self.lut
        new_shade[:start] = self.shade
        for code in range(start, len(chars)):
            ch = chars[code]
            if ch in _EMPTY:
                new_lut[code] = 0
            elif ch in SHADES:
                new_shade[code] = True
                new_lut[code] = self.n_masks
                for py in (0, 1):
                    for px in (0, 1):
                        self._add(self._render(ch, px, py))
            else:
                new_lut[code] = self.n_masks
                self._add(self._render(ch, 0, 0))
        self.lut, self.shade = new_lut, new_shade

    def mask_indices(self, codes: np.ndarray, x0_px: int, y0_px: int) -> np.ndarray:
        """Máscara por celda de un bloque cuya esquina está en (x0_px, y0_px)
        píxeles lógicos del widget (para la fase de los sombreados)."""
        idx = self.lut[codes]
        if self.shade.any():
            sh = self.shade[codes]
            if sh.any():
                rows, cols = codes.shape
                px = (x0_px + np.arange(cols) * self.cell_w) % 2
                py = (y0_px + np.arange(rows) * self.cell_h) % 2
                idx = idx + sh * (py[:, None] * 2 + px[None, :])
        return idx

    @property
    def mask_array(self) -> np.ndarray:
        return self.masks[:self.n_masks]

    # ── Internos ─────────────────────────────────────────────────────────

    def _add(self, mask: np.ndarray):
        if self.n_masks >= len(self.masks):
            grown = np.zeros((len(self.masks) * 2, self.dev_h, self.dev_w), dtype=np.uint8)
            grown[:self.n_masks] = self.masks[:self.n_masks]
            self.masks = grown
        self.masks[self.n_masks] = mask
        self.n_masks += 1

    def _render(self, ch: str, px: int, py: int) -> np.ndarray:
        img = QImage(self.dev_w, self.dev_h, QImage.Format.Format_RGB32)
        img.setDevicePixelRatio(self.dpr)
        img.fill(_BLACK)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        p.setFont(self.font)
        p.setBrushOrigin(-px, -py)
        p.setPen(_WHITE)
        self._draw(p, ch, self.cell_w, self.cell_h, _WHITE, _BLACK)
        p.end()
        bpl = img.bytesPerLine() // 4
        arr = np.frombuffer(img.constBits(), dtype=np.uint32,
                            count=bpl * self.dev_h).reshape(self.dev_h, bpl)
        return (arr[:, :self.dev_w] & 0xFF).astype(np.uint8)   # cobertura 0..255


def qt_draw_glyph(draw_block_element):
    """Función de dibujo del lienzo, para inyectarla en GlyphAtlas."""
    from PySide6.QtCore import QRect

    def draw(painter, ch, cw, rh, fg, bg):
        if not draw_block_element(painter, ch, 0, 0, cw, rh, fg, bg):
            painter.drawText(QRect(0, 0, cw, rh), Qt.AlignmentFlag.AlignCenter, ch)
    return draw
