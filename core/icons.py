"""Iconos SVG para la barra de herramientas.

Todos son paths monochrome en viewBox 0 0 24 24. Se renderizan con el color
que se pase a get_icon() — por defecto blanco para temas oscuros.
"""
from __future__ import annotations

from PySide6.QtGui  import QIcon, QPixmap, QPainter
from PySide6.QtCore import QSize, Qt
from PySide6.QtSvg  import QSvgRenderer

_SIZE = 22   # px del QIcon resultante

# ── SVG paths — viewBox 0 0 24 24, stroke monochrome ─────────────────────────

_SVG: dict[str, str] = {

    "pencil": """
      <path d="M4 20 L8.5 20 L19.5 9 L15.5 5 L4.5 16 Z"
            stroke-linejoin="round"/>
      <path d="M15.5 5 L19.5 9" stroke-linecap="round"/>
      <path d="M4 20 L8.5 20 L8.5 15.5" stroke-linejoin="round" fill="none"/>
    """,

    "eraser": """
      <rect x="3" y="11" width="10" height="7" rx="1"
            transform="rotate(-35 8 14.5)"/>
      <line x1="2" y1="20" x2="22" y2="20" stroke-linecap="round"/>
      <line x1="12.5" y1="7.5" x2="17.5" y2="12.5" stroke-linecap="round"/>
    """,

    "fill": """
      <path d="M5 15 L12 4 L19 15 Q19 20 12 20 Q5 20 5 15 Z"
            stroke-linejoin="round"/>
      <line x1="12" y1="4" x2="9" y2="9" stroke-linecap="round"/>
      <circle cx="20.5" cy="18.5" r="2"/>
      <line x1="18" y1="16" x2="14" y2="12" stroke-linecap="round"/>
    """,

    "eyedropper": """
      <path d="M17 3 L21 7 L11 17 L7 17 L7 13 Z"
            stroke-linejoin="round"/>
      <line x1="14" y1="6" x2="18" y2="10" stroke-linecap="round"/>
      <path d="M7 17 L4 20" stroke-linecap="round"/>
      <circle cx="4.5" cy="19.5" r="1.5" fill="currentColor" stroke="none"/>
    """,

    "selection": """
      <rect x="3" y="3" width="18" height="18" rx="1"
            stroke-dasharray="3 2" fill="none"/>
      <line x1="12" y1="3" x2="12" y2="21" stroke-dasharray="3 2"/>
      <line x1="3" y1="12" x2="21" y2="12" stroke-dasharray="3 2"/>
    """,

    "line": """
      <line x1="4" y1="20" x2="20" y2="4" stroke-linecap="round" stroke-width="2"/>
      <circle cx="4"  cy="20" r="2" fill="currentColor" stroke="none"/>
      <circle cx="20" cy="4"  r="2" fill="currentColor" stroke="none"/>
    """,

    "rect": """
      <rect x="3" y="5" width="18" height="14" rx="1" fill="none"/>
    """,

    "ellipse": """
      <ellipse cx="12" cy="12" rx="9" ry="6" fill="none"/>
      <line x1="12" y1="6"  x2="12" y2="18" stroke-dasharray="2 2"/>
      <line x1="3"  y1="12" x2="21" y2="12" stroke-dasharray="2 2"/>
    """,
}


def _make_svg(key: str, color: str) -> bytes:
    paths = _SVG[key]
    return f"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
     fill="{color}" stroke="{color}" stroke-width="1.5"
     stroke-linecap="round" stroke-linejoin="round">
  {paths}
</svg>""".encode()


def get_icon(name: str, color: str = "#d0d0d0", size: int = _SIZE) -> QIcon:
    """Devuelve un QIcon SVG monochrome del tamaño indicado."""
    renderer = QSvgRenderer(bytearray(_make_svg(name, color)))
    pixmap   = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter  = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
