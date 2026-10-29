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

Ninguno está medido todavía. Las líneas citadas son del 2026-10-29.

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

## Estado

- [ ] Banco en Python sobre `main`
- [ ] Versión NumPy de los candidatos 1 y 3
- [ ] Rama `exp/rust-nucleo` con PyO3 para los candidatos que sigan lentos
- [ ] Decisión, con cifras
