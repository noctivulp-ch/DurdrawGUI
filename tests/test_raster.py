"""Paridad del raster NumPy con el pintado celda a celda de QPainter.

Por qué: el lienzo pasó de un fillRect + drawText por celda a una sola imagen
compuesta con un atlas de glifos (ADR 0002). Si el atlas o la fase de los
sombreados se desajustan, la app sigue funcionando pero pinta otra cosa: un
glifo corrido, un ░ con la trama invertida, un color de la paleta 256 mal
resuelto. Estas pruebas capturan el lienzo por las dos rutas y exigen los
mismos píxeles, en todos los zooms y con desplazamientos impares.
"""

import random

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from core.document import Document
from core.raster import CharTable, composite_codes, rasterize, palette_argb

CHARS = list("@#%&*+=-:.aZ09|/\\") + [chr(c) for c in range(0x2580, 0x25A0)] + ["\x00", " "]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _doc(w=40, h=14, layers=3, seed=5, colors=16):
    rng = random.Random(seed)
    doc = Document(w, h, "256" if colors == 256 else "16")
    doc.add_empty_frame()
    for _ in range(layers - 1):
        doc.add_layer()
    for li, layer in enumerate(doc.layers):
        for f in layer.frames:
            for r in range(h):
                for c in range(w):
                    if rng.random() < (0.9 if li == 0 else 0.3):
                        f.content[r][c] = rng.choice(CHARS)
                        f.newColorMap[r][c] = [rng.randrange(colors), rng.randrange(colors)]
    return doc


def test_composite_codes_coincide_con_composite_frame():
    doc = _doc(layers=4)
    table = CharTable()
    for fi in range(doc.frameCount):
        codes, fg, bg = composite_codes(doc, fi, table)
        ref = doc.composite_frame(fi)
        assert [[table.chars[k] for k in row] for row in codes.tolist()] == ref.content
        assert fg.tolist() == [[p[0] for p in row] for row in ref.newColorMap]
        assert bg.tolist() == [[p[1] for p in row] for row in ref.newColorMap]


def test_capa_oculta_no_cuenta():
    doc = _doc(layers=2)
    doc.layers[1].visible = False
    table = CharTable()
    codes, _, _ = composite_codes(doc, 0, table)
    assert [[table.chars[k] for k in row] for row in codes.tolist()] == doc.composite_frame(0).content


def test_rasterize_pinta_frente_y_fondo_por_mascara():
    masks = np.zeros((2, 2, 2), dtype=np.uint8)
    masks[1, 0, :] = 255                        # máscara 1: fila superior
    pal = palette_argb(["#000000", "#ff0000", "#00ff00"])
    img = rasterize(np.array([[1, 0]]), np.array([[1, 1]]), np.array([[2, 2]]), masks, pal)
    assert img.shape == (2, 4)
    assert img[0, 0] == pal[1] and img[1, 0] == pal[2]   # glifo: frente arriba
    assert (img[:, 2:] == pal[2]).all()                  # vacío: todo fondo
    # El índice de paleta hace módulo, como ColorService.color().
    img2 = rasterize(np.array([[1]]), np.array([[4]]), np.array([[0]]), masks, pal)
    assert img2[0, 0] == pal[1]


def _grab(app, raster: bool):
    cv = app.canvas_widget
    cv._raster_forced_off = not raster
    cv.repaint()
    img = cv.grab().toImage()
    ptr = img.constBits()
    return np.frombuffer(ptr, dtype=np.uint8, count=img.sizeInBytes()).reshape(
        img.height(), img.bytesPerLine()).copy()


@pytest.mark.parametrize("colors", [16, 256])
def test_raster_identico_a_qpainter_en_todos_los_zooms(qapp, colors):
    from ui.app import App
    app = App()
    app.resize(1000, 700)
    app.show()
    qapp.processEvents()
    try:
        app.doc = _doc(colors=colors)
        app._set_color_mode(app.doc.color_format, reset_colors=False)
        app.bus.emit("layers_changed", None)
        app._goto_frame(1)
        cv = app.canvas_widget
        while cv._zoom_idx > 0:
            cv.zoom_out()
        for step in range(9):
            for view in ((0, 0), (3, 1), (-2, -1)):
                cv._view_col, cv._view_row = view   # fases impares de los sombreados
                a, b = _grab(app, True), _grab(app, False)
                # Solo el área del documento: la ruta antigua rellenaba el fondo
                # con fillRect(cw+1, rh+1) y se salía 1 px del borde (ADR 0002).
                x1 = (app.doc.width - view[0]) * cv._cell_w * 4
                y1 = (app.doc.height - view[1]) * cv._cell_h
                x0 = max(0, -view[0]) * cv._cell_w * 4
                y0 = max(0, -view[1]) * cv._cell_h
                diff = np.count_nonzero(a[y0:y1, x0:x1] != b[y0:y1, x0:x1])
                assert diff == 0, f"zoom {step} vista {view}: {diff} bytes distintos"
            cv.zoom_in()
    finally:
        app._dirty = False
        app.close()


# ── Exportación (PIL) ─────────────────────────────────────────────────────────

def _frame_to_pil_celda_a_celda(frame, font, color_format="16"):
    """La implementación anterior de core.io._frame_to_pil, como referencia."""
    from PIL import Image, ImageDraw
    from core import io
    img = Image.new("RGB", (frame.width * io._CELL_W, frame.height * io._CELL_H))
    draw = ImageDraw.Draw(img)
    for row in range(frame.height):
        for col in range(frame.width):
            ch = frame.content[row][col]
            fg, bg = frame.newColorMap[row][col]
            x0, y0 = col * io._CELL_W, row * io._CELL_H
            draw.rectangle([x0, y0, x0 + io._CELL_W - 1, y0 + io._CELL_H - 1],
                           fill=io._palette_rgb(bg, color_format))
            if ch not in (" ", "\x00"):
                draw.text((x0, y0 + 1), ch, fill=io._palette_rgb(fg, color_format), font=font)
    return img


@pytest.mark.parametrize("colors", [16, 256])
def test_exportacion_identica_a_dibujar_celda_a_celda(colors):
    from core import io
    doc = _doc(w=30, h=10, colors=colors)
    font = io._load_font()
    frame = doc.composite_frame(0)
    fmt = "256" if colors == 256 else "16"
    a = np.asarray(io._frame_to_pil(frame, font, fmt))
    b = np.asarray(_frame_to_pil_celda_a_celda(frame, font, fmt))
    assert a.shape == b.shape
    assert np.count_nonzero(a != b) == 0


# ── Minimapa ──────────────────────────────────────────────────────────────────

def _minimapa_pixel_a_pixel(doc, svc, panel_w, panel_h):
    """El bucle anterior de MinimapOverlay._rebuild, como referencia."""
    from ui.minimap import _qcolor, _EMPTY_CHARS
    visual_h = doc.height * 2
    scale = min(panel_w / doc.width, panel_h / visual_h)
    img_w, img_h = max(1, round(doc.width * scale)), max(1, round(visual_h * scale))
    cx, cy = doc.width / img_w, doc.height / img_h
    comp = doc.composite_frame()
    n_pal = svc.count()
    pal = [_qcolor(i, svc).rgb() for i in range(n_pal)]
    out = np.zeros((img_h, img_w), dtype=np.uint32)
    for py in range(img_h):
        row = min(int(py * cy), doc.height - 1)
        for px in range(img_w):
            col = min(int(px * cx), doc.width - 1)
            ch = comp.content[row][col]
            fg, bg = comp.newColorMap[row][col]
            out[py, px] = pal[(fg if ch and ch not in _EMPTY_CHARS else bg) % n_pal]
    return out


@pytest.mark.parametrize("size", [(40, 14), (240, 67), (80, 24)])
def test_minimapa_identico_al_bucle_por_pixel(qapp, size):
    from core.color_service import ColorService
    from core.event_bus import EventBus
    from ui.minimap import MinimapOverlay
    doc = _doc(w=size[0], h=size[1], layers=2)
    svc = ColorService(EventBus())
    img = MinimapOverlay({})._rebuild(doc, svc, 240, 160)
    ptr = img.constBits()
    got = np.frombuffer(ptr, dtype=np.uint32, count=img.height() * img.bytesPerLine() // 4
                        ).reshape(img.height(), img.bytesPerLine() // 4)[:, :img.width()]
    assert np.array_equal(got, _minimapa_pixel_a_pixel(doc, svc, 240, 160))


# ── Caché por frame ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("accion", ["duplicate_frame", "delete_frame", "add_frame"])
def test_cambiar_frames_no_deja_la_cache_desfasada(qapp, accion):
    """Las matrices del lienzo van por índice de frame. Insertar o borrar uno
    desplaza los índices: si no se invalida, tras reproducir la animación el
    lienzo pinta el frame vecino (pasaba antes del 2026-11-08)."""
    from ui.app import App
    app = App()
    app.show()
    qapp.processEvents()
    try:
        doc, cv = app.doc, app.canvas_widget
        while doc.frameCount < 3:
            app.add_frame()
        for i in range(3):
            doc.layers[0].frame_at(i).content[0][0] = "ABC"[i]
        app.bus.emit("layers_changed", None)
        for n in (1, 2, 3, 2):
            app._goto_frame(n)
            cv.repaint()
        getattr(app, accion)()
        for n in range(1, doc.frameCount + 1):
            app._goto_frame(n)
            cv.repaint()
            pintado = cv._char_table.chars[cv._frame_arrays[doc.current_frame_idx][0][0, 0]]
            assert pintado == doc.composite_frame().content[0][0], f"frame {n}"
    finally:
        app._dirty = False
        app.close()
