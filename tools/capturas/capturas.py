#!/usr/bin/env python3
"""Regenera las tres capturas del README (docs/capturas/*.png).

    python tools/capturas/capturas.py

- editor-oscuro.png: la ventana entera en tema oscuro, con el arte de ejemplo.
- editor-claro.png: la misma en tema claro, con el minimapa y otra herramienta.
- temas-corte.png: el lienzo con zoom acercado, mitad en tema oscuro y mitad en
  claro, unidas con un corte diagonal (corte_diagonal.py, el mismo de las otras
  apps de la casa).

El arte se genera aquí mismo (cielo nocturno, luna, montañas y estrellas que
titilan; 256 colores, 4 capas, 8 frames), con semilla fija: no hay arte de
terceros y regenerar da las mismas imágenes. Corre Qt en offscreen con una
configuración temporal: no abre ventanas ni lee ni escribe la del usuario.
Necesita PySide6, Pillow y NumPy.
"""

from __future__ import annotations

import math
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "capturas")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_tmp = tempfile.mkdtemp(prefix="durdrawgui-capturas-")
os.environ["DURDRAW_CONFIG_DIR"] = os.path.join(_tmp, "config")
os.environ["DURDRAW_LOG_DIR"] = os.path.join(_tmp, "logs")
os.environ["DURDRAW_LOG"] = "none"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PIL import Image  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.document import Document  # noqa: E402
from core.theme import DARK, LIGHT  # noqa: E402
from corte_diagonal import componer  # noqa: E402

W, H, FRAMES = 96, 34, 8
SKY = [17, 17, 18, 18, 19, 19, 20, 25, 26, 32, 68, 104]   # azul noche → violeta en el horizonte


def _put(frame, c, r, ch, fg, bg):
    if 0 <= c < W and 0 <= r < H:
        frame.content[r][c] = ch
        frame.newColorMap[r][c] = [fg, bg]


def demo_document() -> Document:
    rng = random.Random(20261108)
    doc = Document(W, H, "256")
    for _ in range(FRAMES - 1):
        doc.add_empty_frame()
    doc.layers[0].name = "Cielo"
    for name in ("Estrellas", "Luna", "Montañas"):
        doc.add_layer(name)

    sky, stars, moon, hills = doc.layers
    horizon = 24
    peaks = [horizon - 2 - int(7 * abs(math.sin(c / 13.0)) + 4 * abs(math.sin(c / 5.3 + 1)))
             for c in range(W)]
    star_pos = [(rng.randrange(W), rng.randrange(horizon - 4), rng.random()) for _ in range(70)]

    for fi in range(FRAMES):
        # Cielo: degradado por filas, con ░▒ para suavizar el salto entre tonos.
        f = sky.frame_at(fi)
        for r in range(H):
            band = min(len(SKY) - 1, r * len(SKY) // horizon)
            nxt = min(len(SKY) - 1, band + 1)
            for c in range(W):
                frac = (r * len(SKY) / horizon) % 1
                ch = "▒" if frac > 0.66 else ("░" if frac > 0.33 else " ")
                _put(f, c, r, ch, SKY[nxt], SKY[band])
        # Estrellas que titilan: cada una cambia de brillo con su propia fase.
        f = stars.frame_at(fi)
        for c, r, ph in star_pos:
            phase = (fi / FRAMES + ph) % 1
            ch, fg = ("*", 231) if phase < 0.25 else (("·", 250) if phase < 0.7 else ("∙", 244))
            band = min(len(SKY) - 1, r * len(SKY) // horizon)
            _put(f, c, r, ch, fg, SKY[band])
        # Luna: disco que sube despacio, con dos cráteres.
        f = moon.frame_at(fi)
        mc, mr = 70 - fi, 9 - fi * 0.4
        for r in range(H):
            for c in range(W):
                d = math.hypot((c - mc) / 2.0, r - mr)
                if d < 4.2:
                    crater = math.hypot((c - mc + 3) / 2.0, r - mr + 1) < 1.1 or \
                        math.hypot((c - mc - 2) / 2.0, r - mr - 1.5) < 0.9
                    _put(f, c, r, "▓" if crater else "█", 187 if crater else 230, 223)
                elif d < 5.2:
                    band = min(len(SKY) - 1, r * len(SKY) // horizon)
                    _put(f, c, r, "░", 186, SKY[band])
        # Montañas y llanura.
        f = hills.frame_at(fi)
        for c in range(W):
            top = peaks[c]
            for r in range(top, H):
                if r == top:
                    _put(f, c, r, "▄", 22, SKY[min(len(SKY) - 1, r * len(SKY) // horizon)])
                elif r < horizon + 1:
                    _put(f, c, r, "▓" if (c + r) % 7 == 0 else "█", 22 if r < top + 3 else 28, 22)
                else:
                    shade = "▒" if (c * 3 + r * 5 + fi) % 11 == 0 else "█"
                    _put(f, c, r, shade, 58 if r > horizon + 4 else 64, 22)
        title = " DurdrawGUI "
        for i, ch in enumerate(title):
            _put(f, 4 + i, H - 3, ch, 230, 52)
    doc.goto_frame(1)
    return doc


def pump(ms=150):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def grab(win) -> Image.Image:
    pump()
    img = win.grab().toImage()
    path = os.path.join(_tmp, "grab.png")
    img.save(path)
    return Image.open(path).convert("RGB")


def main():
    qapp = QApplication.instance() or QApplication([])
    from ui.app import App
    os.makedirs(OUT, exist_ok=True)
    app = App()
    app.resize(1440, 860)
    app.show()
    pump(300)
    app.doc = demo_document()
    app._set_color_mode("256", reset_colors=False)
    app.bus.emit("layers_changed", None)
    app.doc.set_active_layer(3)
    app.bus.emit("layers_changed", None)
    app._goto_frame(1)
    app.set_fg_color(230)
    app.set_bg_color(22)
    cv = app.canvas_widget
    cv.zoom_reset()
    cv.center_view()
    pump(300)

    app.theme_service.apply(DARK)
    a = grab(app)
    a.save(os.path.join(OUT, "editor-oscuro.png"), optimize=True)

    app.theme_service.apply(LIGHT)
    app._goto_frame(4)
    app.select_tool("fill")
    if not app.canvas_widget.minimap.visible:
        app._toggle_minimap()
    grab(app).save(os.path.join(OUT, "editor-claro.png"), optimize=True)

    # Zoom acercado sobre la luna y el horizonte: se ven los glifos y la trama ░▒▓.
    app._toggle_minimap()
    app.select_tool("pencil")
    for _ in range(3):
        cv.zoom_in()
    cv.set_view(36, 2)
    pump(300)
    claro = grab(app)
    app.theme_service.apply(DARK)
    oscuro = grab(app)
    componer(oscuro, claro, 0.035, 3).convert("RGB").save(
        os.path.join(OUT, "temas-corte.png"), optimize=True)

    app._dirty = False
    app.close()
    for name in sorted(os.listdir(OUT)):
        print(os.path.join("docs", "capturas", name))


if __name__ == "__main__":
    main()
