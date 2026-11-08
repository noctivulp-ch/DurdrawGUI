# 0002 — Lienzo y exportación rasterizados con NumPy y un atlas de glifos

- **Estado:** adoptada (2026-11-08).
- **Ámbito:** `core/raster.py`, `ui/glyph_atlas.py`, `ui/canvas.py`, `ui/minimap.py`,
  `core/io.py` (exportación a imagen), `core/document.py` (`composite_frame`),
  `core/grid_copy.py` y las herramientas.
- **Cifras completas:** [`docs/pendientes/rust-modulos.md`](../pendientes/rust-modulos.md).

## Contexto

El plan de rendimiento (`docs/pendientes/rust-modulos.md`, 2026-10-29) sospechaba sobre todo de
`composite_frame()`. Al medir resultó que **`paintEvent` ni siquiera lo usaba**: el lienzo componía
celda a celda con `composite_cell()`, y lo caro era pintar. Cada celda costaba un `fillRect` más un
`drawText`, unos 5 µs solo el `drawText`. Con 16 080 celdas visibles (240×67 con el zoom mínimo)
salían 38–95 ms por repintado y la reproducción se quedaba en 7–25 FPS. El 80 % de exportar un GIF
era PIL rasterizando el mismo glifo en cada celda de cada frame.

Ningún bucle por celda en Python baja de 16 ms con 16 000 celdas, por mucho que se pula. Hacía falta
dejar de pintar celda a celda.

## Decisión

1. **Matrices por frame.** El lienzo guarda, por frame visitado, tres matrices `int32`
   (código de carácter, fg y bg) compuestas de una vez con `core/raster.composite_codes()`. Esa
   función compone de arriba abajo: cada celda se queda con la primera capa opaca. Las matrices no
   dependen del zoom ni de la fuente. Editar invalida solo el frame actual (o la celda, con
   `update_cell`); cambiar capas o frames invalida todo (eventos `layers_changed` y
   `frames_changed`).
2. **Atlas de glifos** (`ui/glyph_atlas.py`). Cada carácter se dibuja una sola vez, blanco sobre
   negro, con el mismo `QPainter` y la misma función de dibujo que usaba el lienzo. Se guarda su
   **cobertura** de 0 a 255: el texto lleva antialiasing aunque el lienzo ponga
   `TextAntialiasing=False`, por la configuración de fontconfig. Los sombreados ░▒▓ tienen 4
   máscaras, una por fase de la trama 2×2, que va alineada al origen del widget.
3. **Baldosas por combinación** (`core/raster.TileCache`). En un frame hay muchas menos combinaciones
   distintas de (glifo, fg, bg) que celdas. Cada combinación se pinta una vez con la mezcla exacta de
   Qt (`blend_pixel`: `s = fg·a; s + bg·(255−alfa(s))`, con el redondeo de `BYTE_MUL`) y se guarda.
   La imagen del repintado sale de un solo *gather* de memoria, que no depende de cuánto texto haya.
4. **Una sola `QImage`** por repintado, con `drawImage`. Los overlays (cursor, selección, guías,
   minimapa) se siguen pintando con `QPainter` encima.
5. **Respaldo**: con un DPR fraccionario (celdas que no son un número entero de píxeles del
   dispositivo) o con `DURDRAW_RASTER=qpainter`, se pinta celda a celda como antes, desde las mismas
   matrices.
6. **Exportación** (`core/io.py`): la misma `TileCache` con la mezcla de Pillow (`BLEND` y `DIV255`)
   y un atlas de máscaras de PIL. Se reproduce también el píxel que los bloques y las líneas de caja
   desbordan sobre la celda de su izquierda: en DejaVu Sans Mono a 13 px es 1 px, y PIL lo dejaba
   encima porque pinta la celda siguiente después.
7. **Minimapa** vectorizado sobre las matrices del lienzo, con el mismo muestreo.

## Lo que se encontró por el camino (y el plan no tenía)

- **El recolector de basura.** El documento tiene millones de listas pequeñas (un par `[fg, bg]` por
  celda, capa y frame: 4,8 millones con 10 capas y 30 frames). Cualquier operación que creara miles
  de listas disparaba pasadas del GC que recorrían el documento entero: 30 `composite_frame` tardaban
  2001 ms con el GC activo y 202 ms sin él. **Arreglo:** no crear esas listas.
  - `composite_frame` comparte los pares de las capas en lugar de copiarlos.
  - Los snapshots de deshacer (`core/grid_copy.py`) copian las filas, no los pares, en lugar de usar
    `deepcopy`.

  Se apoya en un invariante que queda escrito en `core/grid_copy.py`: **un par `[fg, bg]` nunca se
  modifica en su sitio, siempre se sustituye entero**. Lo vigila
  `tests/test_undo.py`: si se introduce una mutación en sitio, la prueba falla (comprobado).
- **Caché desfasada al duplicar o borrar frames** (fallo que ya existía). Las cachés van por índice
  de frame. Duplicar o borrar uno desplazaba los índices y, tras reproducir la animación, el lienzo
  pintaba el frame vecino. Ahora `App` emite `frames_changed` y el lienzo invalida.
  Prueba: `tests/test_raster.py::test_cambiar_frames_no_deja_la_cache_desfasada`.
- **Relleno**: cuatro `deepcopy` del frame entero por trazo y un `update(QRect)` por celda.
  Ahora hay copias por fila y `update_cells()` en lote: por encima de 256 celdas, un solo repintado.

## Paridad

`tests/test_raster.py` captura el lienzo por las dos rutas (raster y celda a celda) en los 9 zooms,
con desplazamientos impares y con paletas de 16 y 256 colores, y exige **0 píxeles distintos** dentro
del documento. Lo mismo para la exportación (contra la implementación anterior, conservada en la
prueba) y para el minimapa.

Única diferencia intencionada: la ruta antigua rellenaba el fondo con `fillRect(cw+1, rh+1)` y dejaba
una franja de 1 px fuera del borde derecho e inferior del documento. El raster no la pinta.

## Resultados

Tabla completa en `docs/pendientes/rust-modulos.md`. En el peor caso, 240×67 con 10 capas:

| | Antes | Después |
|---|---:|---:|
| Repintado con la caché llena, zoom mínimo | 91 ms | 6,5 ms |
| Repintado de un frame nuevo, zoom mínimo | 132 ms | 18,5 ms |
| FPS al reproducir a 30, zoom mínimo | 7 | 31 |
| Minimapa | 31 ms | 8,5 ms |
| GIF de 30 frames | 10,9 s | 1,7 s |

En el 240×67 de 1 capa, el relleno del lienzo entero pasa de 120 a 37 ms. En el 80×24, el repintado
baja de 13–21 ms a 1,2–5,3 ms.

## Por qué no Rust

Con NumPy se cumplen todos los criterios de adopción del plan (30 FPS, repintado por debajo de
16 ms con la caché llena, relleno que no se ve). Lo que queda caro es recorrer las listas de durdraw
en Python y el codificador de GIF de Pillow. Un módulo PyO3 no quita lo primero, porque seguiría
leyendo objetos de Python, y no toca lo segundo. No se creó la rama `exp/rust-nucleo`. Razonamiento
completo en `docs/pendientes/rust-modulos.md`.

## Alternativas descartadas

- **Vectorizar `composite_frame` con NumPy y dejar el pintado celda a celda.** El compositor no era
  el cuello. Además, pasar las listas de durdraw a matrices cuesta lo mismo que componerlas en Python
  (medido: 2,9 ms por capa frente a 1,9 ms de composición entera en un 240×67).
- **Guardar el documento en matrices NumPy** en lugar de listas de durdraw. Quitaría la conversión y
  el GC de raíz, pero toca el modelo, la E/S, las herramientas y los pinceles. Queda anotado como
  siguiente paso si algún día hace falta.
- **Caché de la imagen ya pintada de cada frame.** Con 15 MB por frame a 11×22 px, 30 frames pasan
  de 450 MB. Con las baldosas, el repintado ya cuesta unos 6 ms.
- **Imagen en modo paleta directamente para el GIF**, saltándose la cuantización de Pillow
  (~4 ms por frame). Pillow busca el color más cercano con una caché de 6 bits por canal, y no se
  garantiza el mismo resultado.
