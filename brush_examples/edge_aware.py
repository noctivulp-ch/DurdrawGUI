"""Ejemplo de SmartBrush — pincel 5×5 que no pisa el borde de dibujo/texto
existente. Para instalarlo: copiar este archivo a
~/.config/durdrawgui/brushes/edge_aware.py (o usar "Importar" en la barra
de contexto del lápiz/borrador).
"""

from core.brush import SmartBrush


class EdgeAwareBrush(SmartBrush):
    name        = "Respeta bordes"
    description = "Pincel 5x5 que no pisa el contorno de dibujo/texto existente"
    author      = "ejemplo"

    _RADIUS = 2

    @property
    def footprint(self):
        r = self._RADIUS
        return [(dr, dc) for dr in range(-r, r + 1) for dc in range(-r, r + 1)]

    def paint(self, ctx):
        cells = []
        for dr, dc in self.footprint:
            if ctx.is_edge(dc, dr):
                continue   # dejar intacto el contorno de lo que ya existe
            cells.append((dr, dc, None, None, None))
        return cells
