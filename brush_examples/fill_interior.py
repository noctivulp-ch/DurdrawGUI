"""Ejemplo de SmartBrush — rellena solo el hueco vacío ENCERRADO bajo el
cursor (ej: el interior de un círculo dibujado con líneas), sin derramarse
sobre espacio abierto. Concepto: flood-fill / conectividad (interior vs
exterior).

Un solo clic dentro de una forma cerrada rellena toda la región de una vez —
paint() no está limitado al footprint declarado (que aquí es solo el centro,
para la previsualización); el resultado real depende del análisis del hueco.
"""

from core.brush import SmartBrush


class FillInteriorBrush(SmartBrush):
    name        = "Relleno interior"
    description = "Rellena el hueco vacío encerrado bajo el cursor; no toca espacio abierto"
    author      = "ejemplo"

    @property
    def footprint(self):
        return [(0, 0)]

    def paint(self, ctx):
        if not ctx.is_empty():
            return []
        offsets, reached_edge = ctx.flood_region()
        if reached_edge:
            return []   # espacio abierto (exterior) — no derramar la pintura
        return [(dr, dc, None, None, None) for dc, dr in offsets]
