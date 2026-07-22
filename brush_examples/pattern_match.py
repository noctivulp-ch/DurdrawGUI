"""Ejemplo de SmartBrush — analiza el carácter más frecuente en el área
vecina y pinta con ESE en vez del carácter activo, para continuar una
textura/patrón existente en vez de imponer uno nuevo encima. Concepto:
lectura y análisis de un patrón leído del lienzo (BrushContext.scan)."""

from collections import Counter

from core.brush import SmartBrush


class PatternMatchBrush(SmartBrush):
    name        = "Camuflaje"
    description = "Pinta con el carácter dominante alrededor del cursor (continúa el patrón)"
    author      = "ejemplo"

    _RADIUS = 3

    @property
    def footprint(self):
        return [(0, 0)]

    def paint(self, ctx):
        counts = Counter()
        for row in ctx.scan(-self._RADIUS, -self._RADIUS, self._RADIUS, self._RADIUS):
            for ch, _fg, _bg in row:
                if ch not in (" ", "\x00"):
                    counts[ch] += 1

        if not counts:
            return [(0, 0, None, None, None)]   # nada alrededor: usar el carácter activo

        dominant = counts.most_common(1)[0][0]
        return [(0, 0, dominant, None, None)]
