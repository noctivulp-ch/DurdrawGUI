# Pinceles de ejemplo (SmartBrush)

Cinco pinceles con lógica en Python, cada uno mostrando un concepto distinto
del kit de herramientas de `core.brush.BrushContext`. Ninguno se carga
automáticamente — para probarlos, importalos desde la barra de contexto del
lápiz/borrador ("Importar…") o copiá el archivo a
`~/.config/durdrawgui/brushes/`.

| Archivo | Pincel | Concepto | API usada |
|---|---|---|---|
| `edge_aware.py` | Respeta bordes | evitar pisar el contorno de dibujo/texto existente | `is_edge` |
| `fill_interior.py` | Relleno interior | detectar hueco encerrado vs. espacio abierto | `flood_region`, `is_empty` |
| `spray.py` | Spray | aleatoriedad con densidad decreciente | `random` (stdlib, sin restricciones) |
| `pattern_match.py` | Camuflaje | leer y analizar un patrón del lienzo | `scan` |
| `growth.py` | Crecimiento | autómata celular / bordes orgánicos | `count_neighbors` |

## Referencia de `BrushContext`

Instancia que recibe `paint(ctx)`, con `ctx.col`/`ctx.row` = celda del
cursor y `ctx.fg_char`/`ctx.fg_color`/`ctx.bg_color` = valores activos.
Todos los métodos toman offsets `(dc, dr)` **relativos al cursor**, no
coordenadas absolutas.

| Método | Devuelve |
|---|---|
| `in_bounds(dc, dr)` | si la celda cae dentro del frame |
| `char_at(dc, dr)` | carácter en esa celda (`" "` si está fuera de rango) |
| `colors_at(dc, dr)` | `(fg, bg)` en esa celda |
| `is_empty(dc, dr)` | si la celda está vacía (espacio + sin fondo) |
| `neighbors4(dc, dr)` | offsets de los 4 vecinos ortogonales |
| `neighbors8(dc, dr)` | offsets de los 8 vecinos (con diagonales) |
| `is_edge(dc, dr)` | si la celda linda con un cambio vacío/ocupado |
| `count_neighbors(predicate, dc, dr, diagonal=False)` | cuántos vecinos cumplen `predicate(ch, fg, bg)` |
| `scan(dc0, dr0, dc1, dr1)` | bloque rectangular de `(ch, fg, bg)`, para analizar un patrón |
| `flood_region(dc, dr, max_cells=4000)` | `(offsets, reached_edge)` — BFS del hueco vacío conectado; `reached_edge=True` si toca el borde del frame (heurística de "exterior" si se supera `max_cells` sin cerrarse) |
| `is_interior(dc, dr, max_cells=4000)` | atajo: `not reached_edge` de `flood_region` |

`ctx.frame` da acceso directo al frame si hace falta algo no cubierto arriba
— **no mutarlo**: el undo depende de que todas las escrituras pasen por lo
que `paint()` devuelve.

## Contrato mínimo

```python
from core.brush import SmartBrush

class MiPincel(SmartBrush):
    name        = "Mi pincel"
    description = "..."
    author      = "vos"

    @property
    def footprint(self):
        return [(0, 0)]   # solo para la previsualización del cursor

    def paint(self, ctx):
        # devolver [(dr, dc, ch, fg, bg), ...] — ch/fg/bg en None usan
        # ctx.fg_char/fg_color/bg_color
        return [(0, 0, None, None, None)]
```

## Seguridad

Estos scripts corren con privilegios completos del proceso — sin sandbox.
Mismo modelo de confianza que un addon de Blender o un script de Krita:
usalos si son tuyos o confiás en quien los escribió. Los `.durg`/`.dur`
nunca referencian ni auto-cargan un script — la selección de pincel es
estado local de la UI.
