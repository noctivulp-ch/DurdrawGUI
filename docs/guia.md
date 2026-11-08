# DurdrawGUI

Editor de arte ASCII con soporte de capas y animación por frames. Interfaz gráfica
construida con PySide6/Qt6, basada en el motor de archivos y paletas de
[durdraw](https://github.com/cmang/durdraw) (Sam Foster, BSD 3-Clause).

---

## Características

### Edición

- **Herramientas:** lápiz, borrador, relleno por inundación, cuentagotas, selección
  rectangular, línea, rectángulo y elipse.
- **Pinceles:** 15 formas built-in (cuadrados 1×1–5×5, diamantes, círculos con radio
  1–3, líneas horizontal/vertical, diagonales, cruz). El lápiz interpola posiciones
  intermedias con el algoritmo de Bresenham al arrastrar. Clic derecho pinta con
  fg y bg intercambiados. Los pinceles de usuario persisten en JSON.
- **Colores:** modo 16 colores ANSI y modo 256 colores. Selector de color de frente
  y fondo independientes con intercambio rápido (`X`).
- **Panel de caracteres:** acceso a bloques Unicode completos (organizados por
  rangos del estándar), el set CP-437 original con todos sus símbolos de caja y
  de bloque, flechas y símbolos misceláneos. Pestañas con rebaje automático a
  segunda fila cuando el ancho del panel no alcanza.
- **Undo / redo** ilimitado por sesión, con scope por operación de herramienta
  (no por celda individual).
- **Zoom** de 6 pt a 24 pt en pasos discretos, anclado al cursor del ratón.
  Niveles: 6, 8, 10, 12, 14 *(base)*, 16, 18, 20, 24.
- **Scroll** con espacio + arrastrar (pan) o rueda del ratón. Cursor cruceta fuera
  del área del documento, cursor invisible dentro.
- **Minimapa** flotante con indicador del viewport, activable con `M`. Posición
  configurable (TL / TR / BL / BR). Maneja documentos más pequeños que la vista.

### Capas

- Capas independientes con nombre, visibilidad individual y orden ajustable.
- Compositor de abajo hacia arriba: celda vacía (espacio sobre fondo 0) se trata
  como transparente, permitiendo composición no destructiva entre capas.
- Copiar (`Ctrl+C`) toma solo la capa activa; Copiar fusionado (`Ctrl+Shift+C`) toma lo que se ve, todas las capas visibles. Pegar escribe siempre en la capa activa.

### Animación

- Frames múltiples por documento; todas las capas comparten el mismo contador de
  frames.
- Reproducción con FPS ajustable de 1 a 30 (defecto 8). `Enter` alterna
  reproducción / pausa.
- Navegación: `←` / `→`, `Home` / `End`, `Alt+N` nuevo frame, `Alt+D` duplicar,
  `Alt+C` eliminar.

### Formatos de archivo

| Formato | Descripción |
|---------|-------------|
| `.durg` | Formato nativo — JSON comprimido con gzip. Conserva capas, frames, modo de color y nombres de capas. |
| `.dur`  | Compatibilidad con durdraw — exporta el compuesto aplanado sin información de capas. |
| `.ans`  | Exportación ANSI con secuencias de escape de color. |
| `.png`  | Renderizado del frame activo como imagen rasterizada. |
| `.jpg`  | Igual que PNG con calidad ajustable (defecto 90). |
| `.gif`  | GIF animado con todos los frames. Retardo por frame configurable (defecto 100 ms). |
| `.mp4`  | Exportación de vídeo a 10 fps mediante ffmpeg. |

### Interfaz

- Barra de contexto adaptativa: muestra controles del lápiz (selector de pincel)
  o del zoom según la herramienta activa.
- Barra de estado: posición del cursor en columna/fila, zoom actual, número de
  frame y total.
- Atajos reasignables desde `Edición → Configurar atajos…` con captura de tecla en
  tiempo real y restauración a valores por defecto.
- Temas: oscuro, claro y sistema (qt6ct). El modo sistema desatura la paleta de
  qt6ct al 65% hacia gris para producir superficies neutras con tinte del acento
  del sistema, usando el mismo lenguaje visual que los presets integrados.

---

## Requisitos

### Ejecución desde fuente

- Python ≥ 3.11
- PySide6 ≥ 6.6
- Pillow ≥ 10
- NumPy ≥ 1.24 (el lienzo y la exportación se rasterizan con NumPy: ADR 0002)

```bash
pip install PySide6 Pillow numpy
python main.py
```

### Ejecución desde AppImage

Sin dependencias de Python. Requiere:

- Linux x86\_64
- Wayland o X11
- `qt6ct` instalado en el sistema si se quiere usar el tema personal
  (el AppImage incluye `libqt6ct.so` compilado contra Qt 6.11.1; la configuración
  se lee de `~/.config/qt6ct/qt6ct.conf`)

---

## Uso

```
durdrawgui [opciones] [ARCHIVO]
```

| Opción | Descripción |
|--------|-------------|
| `ARCHIVO` | Archivo `.durg` a abrir al iniciar |
| `--log-level NIVEL` | Tags de log activos: `none` \| `all` \| lista separada por comas (`canvas,tools`) |
| `--log-dir RUTA` | Directorio de salida para los logs |
| `--config-dir RUTA` | Directorio de configuración del usuario |

### Variables de entorno

| Variable | Efecto |
|----------|--------|
| `DURDRAW_LOG` | Equivalente a `--log-level` |
| `DURDRAW_LOG_DIR` | Equivalente a `--log-dir` |
| `DURDRAW_CONFIG_DIR` | Equivalente a `--config-dir` |
| `QT_QPA_PLATFORM` | Plataforma Qt (`wayland` por defecto) |
| `QT_QPA_PLATFORMTHEME` | Tema Qt (`qt6ct` si existe `~/.config/qt6ct/qt6ct.conf`) |
| `DURDRAW_RASTER=qpainter` | Pinta el lienzo celda a celda en vez de con el raster NumPy (para comparar o depurar; ver ADR 0002) |

---

## Atajos de teclado

### Herramientas

| Tecla | Herramienta |
|-------|-------------|
| `B` | Lápiz |
| `E` | Borrador |
| `G` | Relleno por inundación |
| `I` | Cuentagotas |
| `S` | Selección rectangular |
| `L` | Línea |
| `R` | Rectángulo |
| `O` | Elipse |
| `X` | Intercambiar colores fg / bg |

### Edición

| Tecla | Acción |
|-------|--------|
| `Ctrl+Z` | Deshacer |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Rehacer |
| `Ctrl+C` | Copiar selección (capa activa) |
| `Ctrl+Shift+C` | Copiar fusionado (todas las capas visibles) |
| `Ctrl+X` | Cortar selección |
| `Ctrl+V` | Pegar |
| `Ctrl+A` | Seleccionar todo |
| `Escape` | Deseleccionar |
| `Delete` | Borrar contenido de la selección |

### Vista

| Tecla | Acción |
|-------|--------|
| `Ctrl+=` / `Ctrl+-` | Zoom acercar / alejar |
| `Ctrl+0` | Zoom 1:1 |
| `Ctrl+Home` | Centrar lienzo en la vista |
| `M` | Mostrar / ocultar minimapa |
| `Espacio + arrastrar` | Desplazar la vista (pan) |

### Animación

| Tecla | Acción |
|-------|--------|
| `Enter` | Reproducir / pausar |
| `←` / `→` | Frame anterior / siguiente |
| `Home` / `End` | Primer / último frame |
| `Alt+N` | Nuevo frame |
| `Alt+D` | Duplicar frame actual |
| `Alt+C` | Eliminar frame actual |

### Archivo

| Tecla | Acción |
|-------|--------|
| `Ctrl+N` | Nuevo lienzo |
| `Ctrl+O` | Abrir archivo |
| `Ctrl+S` | Guardar |
| `Ctrl+Q` | Salir |

Todos los atajos son reasignables desde `Edición → Configurar atajos…`.

---

## Archivos de usuario

```
~/.config/durdrawgui/
├── prefs.json          # Preferencias generales (tema, minimapa, fuente del canvas)
├── shortcuts.json      # Atajos reasignados (solo los que difieren del defecto)
└── logs/
    ├── app.log         # Arranque, errores fatales
    ├── io.log          # Apertura, guardado, exportación
    ├── theme.log       # Inicialización de tema y cambios
    └── warnings.log    # WARNING y ERROR de todos los subsistemas
```

Los tags `canvas`, `tools`, `doc`, `paint`, `cel`, `history` e `input` están
desactivados por defecto. Se activan con `--log-level canvas,tools` o
`DURDRAW_LOG=all`.

Los pinceles de usuario se guardan en `~/.config/durdrawgui/brushes/`.

---

## Tests

90 pruebas en 8 módulos, con pytest. Las de interfaz corren en Qt `offscreen` (sin ventanas) y
con una configuración temporal, sin tocar la del usuario (`tests/conftest.py`):

```bash
pytest tests/
```

| Módulo | Cobertura |
|--------|-----------|
| `test_document.py` | Compositor de capas, frames, serialización `.durg` / `.dur`, round-trip con 2 capas y 3 frames |
| `test_movie.py` | Frames, colormap, duplicación, eliminación |
| `test_tools.py` | Bresenham, contornos de rect y elipse, flood fill |
| `test_color_service.py` | Modos 16/256, paleta, eventos del bus |
| `test_file.py` | Round-trip de dimensiones, contenido y colormap |
| `test_input_e2e.py` | Ratón, teclado y tableta con eventos Qt reales sobre la ventana entera |
| `test_undo.py` | Deshacer y rehacer con cada herramienta y con varias capas |
| `test_raster.py` | Paridad píxel a píxel del raster NumPy con QPainter (lienzo), con Pillow (exportación) y del minimapa; caché por frame |

---

## Compilación

El build produce un AppImage de ~51 MB con Python 3.11 y Qt 6.11.1 incluidos.

### Requisitos del entorno de build

- Python 3.11 (`python3.11`)
- `patchelf`
- `appimagetool` en `$PATH`
- `qt6ct` instalado en el sistema (para copiar `libqt6ct.so`)

### Pasos

```bash
# 1. Preparar entorno Python 3.11
python3.11 -m venv .venv311
.venv311/bin/pip install nuitka PySide6 Pillow numpy

# 2. Compilar
.venv311/bin/python -m nuitka \
  --standalone \
  --enable-plugin=pyside6 \
  --include-qt-plugins=sensible,imageformats,iconengines,platformthemes \
  --include-data-dir=core/durdraw=core/durdraw \
  --output-dir=dist/nuitka311 \
  --output-filename=durdrawgui \
  main.py

# 3. Incluir plugin qt6ct del sistema
#    Requiere que la versión de Qt del sistema coincida con PySide6 pip
cp /usr/lib/qt6/plugins/platformthemes/libqt6ct.so \
   dist/nuitka311/main.dist/PySide6/qt-plugins/platformthemes/

# 4. Construir AppDir
mkdir -p dist/DurdrawGUI.AppDir/usr/bin
cp -r dist/nuitka311/main.dist/. dist/DurdrawGUI.AppDir/usr/bin/

cat > dist/DurdrawGUI.AppDir/AppRun << 'EOF'
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=$(dirname "$SELF")
QT6CT_CONF="$HOME/.config/qt6ct/qt6ct.conf"
if [ -f "$QT6CT_CONF" ]; then
    export QT_QPA_PLATFORMTHEME=qt6ct
else
    echo "DurdrawGUI: tema Qt personal no encontrado en $QT6CT_CONF — usando Fusion" >&2
fi
export QT_QPA_PLATFORM=wayland
exec "$HERE/usr/bin/durdrawgui" "$@"
EOF
chmod +x dist/DurdrawGUI.AppDir/AppRun

# .desktop, icono y empaquetado — ver BUILD.md

# 5. Empaquetar
appimagetool dist/DurdrawGUI.AppDir dist/DurdrawGUI-x86_64.AppImage
```

Ver `BUILD.md` para el procedimiento completo y las notas sobre compatibilidad
de versiones Qt.

---

## Estado del proyecto

La interfaz está completa y funcional. Rendimiento medido y resuelto (ADR 0002): 30 FPS al
reproducir incluso un 240×67 con 10 capas. Pendientes, con detalle en el `ToDo.md` de desarrollo:

- **Fase 11:** importación ANSI e imagen, y exportar capas por separado.
- **Pendientes menores:** icono de aplicación definitivo; iconos de la barra de herramientas poco
  visibles en el tema claro.

---

## Licencia

El código fuente es de acceso público bajo una licencia propietaria con fuente
visible — ver archivo `LICENSE` para los términos completos. Resumen:

- **Uso personal y organizacional:** permitido sin restricciones.
- **Modificación para uso propio:** permitida con atribución al autor original.
- **Redistribución de código modificado:** permitida si el cambio es sustancial,
  se incluyen créditos explícitos, y no se usa el nombre "DurdrawGUI".
- **Distribución de builds (binarios):** prohibida en cualquier forma.
- **Canal oficial de distribución:** [Patreon del autor](https://www.patreon.com/cw/NoctiVulp).

`core/durdraw/` contiene código de [durdraw](https://github.com/cmang/durdraw)
de Sam Foster, licenciado bajo **BSD 3-Clause**. Sus términos originales aplican
a ese código de forma independiente.
