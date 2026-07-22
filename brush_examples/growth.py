"""Ejemplo de SmartBrush — solo pinta celdas vacías que ya tienen suficientes
vecinos ocupados, generando un borde irregular/orgánico en vez de un trazo
geométrico duro (como musgo o coral creciendo desde lo ya dibujado).
Concepto: conteo de vecinos / autómata celular (BrushContext.count_neighbors).
"""

from core.brush import SmartBrush


def _occupied(ch, _fg, _bg) -> bool:
    return ch not in (" ", "\x00")


class GrowthBrush(SmartBrush):
    name        = "Crecimiento"
    description = "Solo pinta celdas con 2+ vecinos ya ocupados (bordes orgánicos)"
    author      = "ejemplo"

    _RADIUS        = 3
    _MIN_NEIGHBORS = 2

    @property
    def footprint(self):
        r = self._RADIUS
        return [(dr, dc) for dr in range(-r, r + 1) for dc in range(-r, r + 1)]

    def paint(self, ctx):
        cells = []
        for dr, dc in self.footprint:
            if not ctx.is_empty(dc, dr):
                continue   # no repinta lo que ya existe
            occupied = ctx.count_neighbors(_occupied, dc, dr, diagonal=True)
            if occupied >= self._MIN_NEIGHBORS:
                cells.append((dr, dc, None, None, None))
        return cells
