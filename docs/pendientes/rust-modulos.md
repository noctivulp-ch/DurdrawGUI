# Módulos candidatos a Rust: medir antes de adoptar

Pedido del dueño el 2026-10-29: «deja una nota en el repo para ver qué módulos se pueden escribir en
Rust y medirlos para mejorar el rendimiento en una rama nueva; si es significativo, se adopta».

## Por qué aquí sí y en otras apps no

En el resto del portafolio, los cuellos de botella que Rust resolvería a fuerza bruta ya se
resolvieron con arquitectura. En VulpTiketing eran consultas N+1, índices que faltaban y el raster
del texto tallado; no era el lenguaje. DurdrawGUI es distinto: es una app de dibujo y su trabajo
pesado son bucles de Python puro sobre celdas. El dueño reconoce que en la arquitectura de apps de
dibujo su conocimiento es limitado, así que una solución de arquitectura puede quedarse corta; ahí
Rust puede aportar potencia de verdad. Análisis completo en el vault:
`AppCreator/conceptos/rust-factibilidad.md`.

## Candidatos, por orden de sospecha

Las líneas citadas son del 2026-10-29. **Resultado de medirlos al final del documento**: el orden de sospecha no era el real.

| # | Dónde | Qué hace | Por qué se sospecha |
|---|---|---|---|
| 1 | `core/document.py:131` `composite_frame()` | Compone todas las capas de un frame | Doble bucle por cada capa: 80×24×5 = 9600 iteraciones por render (Rev-2 de `ToDo.md`) |
| 2 | `ui/canvas.py:699` `paintEvent()` | Pinta celda a celda con `drawText` | Un `drawText` por celda visible en cada repintado. Rust no puede usar el `QPainter`, pero sí puede rasterizar el frame a un búfer RGBA con un atlas de glifos, y Qt lo pega como una sola `QImage` |
| 3 | `core/document.py:166` `composite_cell()` | Compone una celda | Se llama una vez por pincelada; el relleno la dispara miles de veces |
| 4 | `core/brush.py:143` `flood_region()` y `tools/fill.py` | Relleno por inundación | BFS en Python, con tope de 4000 celdas |
| 5 | `ui/minimap.py:155` | Construye la imagen del minimapa | Bucle por píxel |
| 6 | `core/io.py:287` `_frame_to_pil()` | Exporta frames a PIL para GIF, PNG y MP4 | Se repite por cada frame de la animación |
| 7 | `core/io.py`, `core/durdraw/` | Carga `.dur`, `.durg` y ANSI | Solo importa con archivos grandes |

## Método

1. **Rama** `exp/rust-nucleo`. `main` no se toca hasta decidir.
2. **Banco primero, en Python y en `main`**. Con documentos de 80×24 y de 240×67
   (`blackhole-smooth-240x67.dur`), con 1, 5 y 10 capas y con 30 frames, medir:
   - ms por `composite_frame` y por `composite_cell`;
   - ms por `paintEvent` completo;
   - FPS reales al reproducir a 30;
   - ms de un relleno de 4000 celdas;
   - ms de exportar un GIF.

   Se repite cada medida y se descarta la primera corrida. El guion del banco va a `scripts/`.
3. **Contrincante honesto**: antes de comparar con Rust, probar la versión NumPy del candidato
   (una matriz por capa). Si NumPy basta, gana: no añade toolchain.
4. **Rust con PyO3 y maturin**, en un crate `rust/` dentro del repo. La interfaz pública sigue
   siendo la de Python: misma firma y mismas pruebas (`tests/test_document.py`), y la versión
   Python se queda como respaldo si el módulo nativo no está.
5. Anotar las cifras de las tres versiones (Python, NumPy y Rust) en este documento.

## Criterio de adopción

Se adopta en `main` si la mejora se **nota en el uso**, no solo en el banco. Por ejemplo:

- la reproducción a 30 FPS pasa de fallar a cumplirse en el documento grande;
- un repintado pasa de más de 16 ms a menos;
- el relleno deja de verse.

Y además Rust tiene que ganar a NumPy por un margen claro. Si solo mejora cifras que no se sienten,
no compensa el costo fijo:

- `rustc` en el build;
- Nuitka empaquetando una extensión nativa;
- wheels por plataforma.

Adoptar un módulo es una decisión de arquitectura y lleva su ADR en `docs/decisiones/`.

## Estado (2026-11-08): medido y resuelto sin Rust

- [x] Banco en Python sobre `main` (`scripts/bench_rendimiento.py`, entorno local; resultados en
  [`bench/`](bench/))
- [x] Variante NumPy y de arquitectura de los candidatos que resultaron ser cuellos reales
- [x] Decisión, con cifras: **se adopta la variante NumPy** ([ADR 0002](../decisiones/0002-raster-numpy.md)).
  **No se crea la rama `exp/rust-nucleo`**: con NumPy se cumplen todos los criterios de adopción y
  no queda ningún cuello que se note en el uso para que Rust lo gane.

### Cómo se midió

App real en Qt `offscreen` (raster de CPU, el mismo `QPainter` que en Wayland) con una ventana de
1600×1000 (lienzo de 1198×879 px). Documentos de 80×24 y 240×67, con 1, 5 y 10 capas y 30 frames. La
capa base del 240×67 son los frames de `blackhole-smooth-240x67.dur` y el resto es sintético con
semilla fija. Cada medida se repite 7 veces, se descarta la primera y se informa la mediana. «Antes»
es el commit de la fase 1 (`feat: entrada repartida…`), corrido justo después de «Después», en la
misma sesión y sin otra carga. Python 3.14.9, Qt 6.12.0, NumPy 2.5.4.

### El plan, revisado contra las mediciones

| # | Candidato del plan | ¿Era cuello? | Qué se hizo |
|---|---|---|---|
| 1 | `composite_frame()` | **No en el lienzo**: `paintEvent` no lo usa. Sí en la exportación y el minimapa, por el GC (ver abajo) | De arriba abajo y sin crear listas por celda: de 17 a 5,5 ms con 10 capas |
| 2 | `paintEvent()` | **Sí, el principal**: `drawText` por celda, 13–132 ms | Raster NumPy con atlas de glifos y baldosas: de 1,2 a 18,5 ms |
| 3 | `composite_cell()` | No: 0,25 µs por llamada. El cuello era el `update(QRect)` y el `deepcopy` alrededor | `update_cells()` en lote. Sigue igual de rápido |
| 4 | Relleno | Sí, pero por los cuatro `deepcopy` y el repintado celda a celda, no por el BFS | Copias por fila y repintado en lote: de 120 a 37 ms en el lienzo entero |
| 5 | Minimapa | Sí si está visible: 14–31 ms en cada frame de la reproducción | Muestreo vectorizado sobre las matrices del lienzo: 0,7–8,5 ms |
| 6 | `_frame_to_pil()` | Sí: PIL rasterizaba el glifo en cada celda (el 80 % del GIF) | Atlas de PIL y baldosas: GIF de 5,1 → 1,2 s y de 10,9 → 1,7 s |
| 7 | Carga de archivos | No medido como cuello; no se tocó | — |
| — | **No estaba en el plan:** el recolector de basura | **Sí**: 30 `composite_frame` tardaban 2001 ms con el GC activo y 202 ms sin él | No crear listas por celda (composición y snapshots); invariante en `core/grid_copy.py` |
| — | **No estaba en el plan:** caché desfasada al duplicar o borrar frames | Fallo que ya existía, no de rendimiento | Evento `frames_changed` |

Lo que el plan suponía y no se cumplió: vectorizar el compositor con NumPy no sirve mientras el
modelo sean listas de durdraw. Convertirlas a matrices cuesta 2,9 ms por capa en un 240×67, más que
componerlas en Python (1,9 ms).

### Por qué no Rust

Criterio del documento: Rust entra solo si NumPy no basta, y además ganándole por un margen claro en
algo que se note. Tras la variante NumPy:

- la reproducción da 30 FPS en todos los casos, incluida la primera vuelta;
- el repintado con la caché llena no pasa de 8 ms, y un frame nuevo, de 18,5 ms (presupuesto: 33 ms);
- el relleno del lienzo entero tarda 37 ms.

Lo que queda caro:

- `composite_codes()`: recorrer las listas de durdraw en Python, 1–10 ms por frame nuevo. Un módulo
  PyO3 seguiría leyendo objetos de Python, así que la ganancia sería pequeña y no se notaría.
- La cuantización y el codificador LZW de Pillow: unos 0,5 s por GIF de 30 frames, en C, fuera del
  alcance de un módulo propio.
- El `drawImage` de Qt.

Ninguno se nota en el uso, y ninguno justifica el costo fijo de `rustc` en el build, Nuitka con una
extensión nativa y wheels por plataforma. Si algún día hiciera falta, el paso previo no sería Rust,
sino guardar el documento en matrices en lugar de listas.

### Cifras

Tiempos en ms; FPS reales al reproducir a 30 (el tope del temporizador es 30,3). «—» quiere decir
que en 4 s no se completó la primera vuelta.

**80x24, 1 capa**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 0.2 | 0.1 |
| composite_cell × frame entero (ms) | 0.5 | 0.4 |
| repintado, caché llena, zoom base (ms) | 13.2 | 2.9 |
| repintado, frame nuevo, zoom base (ms) | 14.1 | 3.3 |
| repintado, caché llena, zoom mínimo (ms) | 12.5 | 1.2 |
| repintado, frame nuevo, zoom mínimo (ms) | 13.4 | 2.0 |
| FPS a 30, 1.ª vuelta, zoom base | 31.2 | 31.4 |
| FPS a 30, estable, zoom base | 31.3 | 31.2 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 31.2 | 31.1 |
| FPS a 30, estable, zoom mínimo | 31.2 | 31.2 |
| minimapa (ms) | 14.3 | 0.7 |
| relleno del lienzo, 1920 celdas (ms) | 27.9 | 6.7 |
| GIF de 30 frames (ms) | 1182 | 242 |

**80x24, 5 capas**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 0.8 | 0.3 |
| composite_cell × frame entero (ms) | 1.8 | 1.7 |
| repintado, caché llena, zoom base (ms) | 14.6 | 3.5 |
| repintado, frame nuevo, zoom base (ms) | 20.1 | 5.3 |
| repintado, caché llena, zoom mínimo (ms) | 13.4 | 1.5 |
| repintado, frame nuevo, zoom mínimo (ms) | 15.9 | 2.3 |
| FPS a 30, 1.ª vuelta, zoom base | 28.1 | 31.3 |
| FPS a 30, estable, zoom base | 31.3 | 31.3 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 31.3 | 31.4 |
| FPS a 30, estable, zoom mínimo | 31.2 | 31.2 |
| minimapa (ms) | 14.4 | 0.8 |

**80x24, 10 capas**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 1.3 | 0.4 |
| composite_cell × frame entero (ms) | 3.8 | 3.9 |
| repintado, caché llena, zoom base (ms) | 14.3 | 5.0 |
| repintado, frame nuevo, zoom base (ms) | 20.4 | 5.0 |
| repintado, caché llena, zoom mínimo (ms) | 13.7 | 1.8 |
| repintado, frame nuevo, zoom mínimo (ms) | 20.7 | 5.3 |
| FPS a 30, 1.ª vuelta, zoom base | 29.6 | 31.2 |
| FPS a 30, estable, zoom base | 31.3 | 31.3 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 31.3 | 31.4 |
| FPS a 30, estable, zoom mínimo | 31.3 | 31.3 |
| minimapa (ms) | 15.7 | 1.3 |
| GIF de 30 frames (ms) | 1343 | 268 |

**240x67, 1 capa**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 2.0 | 1.0 |
| composite_cell × frame entero (ms) | 4.0 | 4.0 |
| repintado, caché llena, zoom base (ms) | 14.5 | 5.4 |
| repintado, frame nuevo, zoom base (ms) | 18.7 | 9.7 |
| repintado, caché llena, zoom mínimo (ms) | 36.9 | 6.2 |
| repintado, frame nuevo, zoom mínimo (ms) | 46.3 | 13.2 |
| FPS a 30, 1.ª vuelta, zoom base | 31.1 | 31.4 |
| FPS a 30, estable, zoom base | 31.3 | 31.3 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 20.6 | 31.2 |
| FPS a 30, estable, zoom mínimo | 25.2 | 31.2 |
| minimapa (ms) | 16.0 | 3.5 |
| relleno de 4000 celdas (ms) | 62.5 | 17.4 |
| relleno del lienzo, 16 080 celdas (ms) | 120 | 36.6 |
| GIF de 30 frames (ms) | 5054 | 1220 |

**240x67, 5 capas**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 7.9 | 3.2 |
| composite_cell × frame entero (ms) | 16.1 | 16.5 |
| repintado, caché llena, zoom base (ms) | 26.2 | 7.4 |
| repintado, frame nuevo, zoom base (ms) | 33.4 | 11.9 |
| repintado, caché llena, zoom mínimo (ms) | 82.8 | 6.7 |
| repintado, frame nuevo, zoom mínimo (ms) | 100 | 15.5 |
| FPS a 30, 1.ª vuelta, zoom base | 29.4 | 31.5 |
| FPS a 30, estable, zoom base | 31.4 | 31.3 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 9.7 | 31.3 |
| FPS a 30, estable, zoom mínimo | 12.4 | 31.3 |
| minimapa (ms) | 22.2 | 6.4 |

**240x67, 10 capas**

| Medida | Antes | Después |
|---|---:|---:|
| composite_frame (ms) | 17.1 | 5.5 |
| composite_cell × frame entero (ms) | 32.0 | 31.9 |
| repintado, caché llena, zoom base (ms) | 29.1 | 7.6 |
| repintado, frame nuevo, zoom base (ms) | 41.7 | 16.5 |
| repintado, caché llena, zoom mínimo (ms) | 90.6 | 6.5 |
| repintado, frame nuevo, zoom mínimo (ms) | 132 | 18.5 |
| FPS a 30, 1.ª vuelta, zoom base | 22.8 | 31.3 |
| FPS a 30, estable, zoom base | 31.4 | 31.3 |
| FPS a 30, 1.ª vuelta, zoom mínimo | 7.4 | 31.1 |
| FPS a 30, estable, zoom mínimo | — | 31.3 |
| minimapa (ms) | 31.2 | 8.5 |
| GIF de 30 frames (ms) | 10940 | 1654 |
