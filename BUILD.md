# DurdrawGUI — Plan de compilación (Nuitka + AppImage)

## Estado de herramientas

- `patchelf` 0.19.1 — instalado (pacman)
- `nuitka` 4.1.3 — en `.venv311/` (Python 3.11)
- `appimagetool` — instalado en `/usr/local/bin/appimagetool`
- Python 3.11 venv: `.venv311/` con PySide6 6.11.1, Pillow 12.3.0

**Nota sobre Python:** usar siempre el venv 3.11, no el Python del sistema (3.14).
Nuitka 4.1.3 tiene soporte experimental para 3.14 que falla en runtime con
`SystemError: Objects/funcobject.c:446` al pasar funciones Python a extensiones C.

---

## Implementación actual (completada)

- [x] `core/log.py` — `_resolve_log_dir()` detecta contexto frozen/AppImage y redirige a `~/.config/durdrawgui/logs/`
- [x] About dialog — `ui/about.py` + entrada en menú Ayuda → Acerca de
- [x] CLI flags — `argparse` en `main.py` para `--log-level`, `--log-dir`, `--config-dir`
- [x] Env vars — `DURDRAW_LOG`, `DURDRAW_LOG_DIR`, `DURDRAW_CONFIG_DIR`
- [x] qt6ct — `libqt6ct.so` del sistema copiado, AppRun lo detecta, ThemeService avisa si falta

---

## Build

### Paso 1 — Compilar con Nuitka (Python 3.11)

```bash
cd DurdrawGUI

.venv311/bin/python -m nuitka \
  --standalone \
  --enable-plugin=pyside6 \
  --include-qt-plugins=sensible,imageformats,iconengines,platformthemes \
  --include-data-dir=core/durdraw=core/durdraw \
  --output-dir=dist/nuitka311 \
  --output-filename=durdrawgui \
  main.py
```

**Familias de plugins válidas** en PySide6 6.11.1 pip: `sensible`, `imageformats`,
`iconengines`, `platformthemes`. Las familias `svg` y `styles` no existen en esta
versión pip (existen en Qt del sistema, pero no se exponen al pip wheel).

Esto genera `dist/main.dist/` con el binario y todas las dependencias Qt.

### Paso 1b — Incluir libqt6ct.so del sistema

El plugin `libqt6ct.so` viene del paquete `qt6ct` del sistema, no de PySide6 pip.
Como el sistema tiene Qt 6.11.1 (igual que PySide6 6.11.1), el ABI es compatible.

```bash
cp /usr/lib/qt6/plugins/platformthemes/libqt6ct.so \
   dist/nuitka311/main.dist/PySide6/qt-plugins/platformthemes/
```

Si la versión del sistema cambia, verificar compatibilidad antes de copiar.

### Paso 2 — Crear AppDir

```bash
mkdir -p dist/DurdrawGUI.AppDir/usr/{bin,lib,share/applications,share/icons/hicolor/256x256/apps}

# Binario y libs (desde nuitka311, no desde dist/main.dist)
cp -r dist/nuitka311/main.dist/. dist/DurdrawGUI.AppDir/usr/bin/

# Icono (placeholder — reemplazar con PNG real en assets/durdrawgui.png)
# cp assets/durdrawgui.png dist/DurdrawGUI.AppDir/usr/share/icons/hicolor/256x256/apps/durdrawgui.png

# .desktop
cat > dist/DurdrawGUI.AppDir/durdrawgui.desktop << 'EOF'
[Desktop Entry]
Name=DurdrawGUI
Comment=Editor de arte ASCII con animación
Exec=durdrawgui
Icon=durdrawgui
Type=Application
Categories=Graphics;
EOF

# AppRun — detecta qt6ct del sistema
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

# Symlinks requeridos por AppImage
ln -sf usr/share/icons/hicolor/256x256/apps/durdrawgui.png dist/DurdrawGUI.AppDir/durdrawgui.png
```

### Paso 3 — Empaquetar

```bash
appimagetool dist/DurdrawGUI.AppDir dist/DurdrawGUI-x86_64.AppImage
```

### Paso 4 — Probar

```bash
chmod +x dist/DurdrawGUI-x86_64.AppImage
./dist/DurdrawGUI-x86_64.AppImage
```

---

## Notas técnicas

### Por qué standalone (no onefile)
`--onefile` descomprime a `/tmp` en cada arranque (~3-5s de delay). Con `--standalone`
el AppImage monta en el mismo directorio, arranque instantáneo.

### Qt plugins necesarios (PySide6 6.11.1 pip)
- `sensible` — incluye xcb, wayland, opengl, egl
- `imageformats` — PNG, JPEG, GIF, etc. (equivale a `svg` en el wheel pip)
- `iconengines` — motor de iconos SVG
- `platformthemes` — qt6ct, gtk3 (libqt6ct.so se copia manualmente del sistema)

Las familias `svg` y `styles` del sistema Qt no están expuestas en el wheel pip —
usarlas en `--include-qt-plugins` falla con `FATAL: no Qt plugin family 'svg'`.

### Problema de logs en AppImage
`core/log.py` escribe en `_APP_DIR/logs/` donde `_APP_DIR = Path(__file__).parent.parent`.
En AppImage, `__file__` apunta dentro del squashfs read-only → crash al intentar crear `logs/`.
Solución: redirigir a `Path.home() / ".config" / "durdrawgui" / "logs"` antes de distribuir.

### Icono
Necesitamos un PNG de 256×256 en `assets/durdrawgui.png`. Por ahora el AppDir
no incluye icono real (el .desktop fallback usa el nombre sin ruta).
