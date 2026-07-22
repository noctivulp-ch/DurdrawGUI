"""Ejemplo de SmartBrush — spray aleatorio con densidad decreciente hacia el
borde del radio. Concepto: aleatoriedad (stdlib `random`, sin restricciones)."""

import random

from core.brush import SmartBrush


class SprayBrush(SmartBrush):
    name        = "Spray"
    description = "Salpicado aleatorio, más denso cerca del centro"
    author      = "ejemplo"

    _RADIUS  = 4
    _DENSITY = 0.35   # probabilidad máxima (en el centro) de estampar una celda

    @property
    def footprint(self):
        r = self._RADIUS
        return [(dr, dc) for dr in range(-r, r + 1) for dc in range(-r, r + 1)
                if dr * dr + dc * dc <= r * r]

    def paint(self, ctx):
        cells = []
        for dr, dc in self.footprint:
            dist   = (dr * dr + dc * dc) ** 0.5
            chance = self._DENSITY * max(0.0, 1 - dist / self._RADIUS)
            if random.random() < chance:
                cells.append((dr, dc, None, None, None))
        return cells
