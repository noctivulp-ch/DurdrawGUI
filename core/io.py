"""
Serialización, deserialización y exportación de documentos.

Responsabilidad única: traducir entre Document y representaciones externas
(.durg, .dur, ANSI). App.py delega aquí toda la lógica de archivo.
"""

import json
import gzip
import os

from core.document import Document, Layer
import core.log as log

_log = log.get("io")


# ── Tablas de color ANSI ───────────────────────────────────────────────────────

_FG_MAP = {
    0: "30", 1: "31", 2: "32", 3: "33",
    4: "34", 5: "35", 6: "36", 7: "37",
    8: "90", 9: "91", 10: "92", 11: "93",
    12: "94", 13: "95", 14: "96", 15: "97",
}
_BG_MAP = {
    0: "40", 1: "41", 2: "42", 3: "43",
    4: "44", 5: "45", 6: "46", 7: "47",
    8: "100", 9: "101", 10: "102", 11: "103",
    12: "104", 13: "105", 14: "106", 15: "107",
}


def _ansi_color_seq(fg, bg):
    f = _FG_MAP.get(fg % 16, "37")
    b = _BG_MAP.get(bg % 16, "40")
    return f"\x1b[{f};{b}m"


# ── Conversión Document ↔ dict ─────────────────────────────────────────────────

def to_durg(doc):
    """Serializa el documento completo con todas las capas (formato .durg)."""
    layers_data = []
    for layer in doc.layers:
        frames_data = []
        for i in range(doc.frameCount):
            fr = layer.frame_at(i)
            cmap = [[fr.newColorMap[r][c] for r in range(doc.height)]
                    for c in range(doc.width)]
            frames_data.append({
                "contents": ["".join(fr.content[r]) for r in range(doc.height)],
                "colorMap": cmap,
            })
        layers_data.append({
            "name": layer.name,
            "visible": layer.visible,
            "frames": frames_data,
        })
    return {
        "DurGUI": {
            "version": 1,
            "columns": doc.width,
            "lines": doc.height,
        },
        "layers": layers_data,
    }


def to_dur(doc):
    """Exporta el compuesto aplanado en formato .dur (compatibilidad con durdraw)."""
    frames_data = []
    for i in range(doc.frameCount):
        fr = doc.composite_frame(frame_idx=i)
        cmap = [[fr.newColorMap[r][c] for r in range(doc.height)]
                for c in range(doc.width)]
        frames_data.append({
            "frameNumber": len(frames_data) + 1,
            "delay": 1,
            "contents": ["".join(fr.content[r]) for r in range(doc.height)],
            "colorMap": cmap,
        })
    return {
        "DurMovie": {
            "formatVersion": 7,
            "colorFormat": doc.color_format,
            "preferredFont": "fixed",
            "encoding": "utf-8",
            "name": "", "artist": "",
            "framerate": 10,
            "columns": doc.width,
            "lines": doc.height,
            "frames": frames_data,
        }
    }


def from_dur(data):
    """Crea un Document de una sola capa a partir de un dict .dur."""
    dm = data["DurMovie"]
    w, h = dm["columns"], dm["lines"]
    color_fmt = str(dm.get("colorFormat", "16"))
    doc = Document(w, h, color_format=color_fmt)
    layer = doc.layers[0]
    for i, fd in enumerate(dm["frames"]):
        if i == 0:
            fr = layer.frames[0]
        else:
            doc.add_empty_frame()
            fr = layer.frames[-1]
        for row_i, line in enumerate(fd["contents"]):
            if row_i < h:
                fr.content[row_i] = list(line.ljust(w))[:w]
        cmap = fd["colorMap"]
        for c in range(w):
            for r in range(h):
                pair = cmap[c][r] if c < len(cmap) and r < len(cmap[c]) else [7, 0]
                fr.newColorMap[r][c] = list(pair)
    doc.goto_frame(1)
    return doc


def from_durg(data):
    """Crea un Document con múltiples capas a partir de un dict .durg."""
    dg = data["DurGUI"]
    w, h = dg["columns"], dg["lines"]
    doc = Document(w, h)
    layers = []

    for ld in data["layers"]:
        layer = Layer(ld["name"], w, h)
        layer.visible = ld.get("visible", True)
        for i, fd in enumerate(ld["frames"]):
            if i == 0:
                fr = layer.frames[0]
            else:
                layer.add_empty_frame()
                fr = layer.frames[-1]
            for row_i, line in enumerate(fd["contents"]):
                if row_i < h:
                    fr.content[row_i] = list(line.ljust(w))[:w]
            cmap = fd["colorMap"]
            for c in range(w):
                for r in range(h):
                    pair = cmap[c][r] if c < len(cmap) and r < len(cmap[c]) else [7, 0]
                    fr.newColorMap[r][c] = list(pair)
        layers.append(layer)

    doc._reset_layers(layers)
    return doc


# ── Operaciones de archivo ─────────────────────────────────────────────────────

def load(path):
    """Carga un .durg o .dur desde disco. Devuelve un Document."""
    size = os.path.getsize(path)
    _log.info(f"load  path={path}  size={size:,}B")
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        _log.debug("load  formato: gzip")
    except gzip.BadGzipFile:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _log.debug("load  formato: json plano")
    fmt = "durg" if "DurGUI" in data else "dur"
    _log.info(f"load  fmt={fmt}")
    if fmt == "durg":
        return from_durg(data)
    return from_dur(data)


def save(doc, path):
    """Guarda en .durg (con capas) o .dur (aplanado) según la extensión."""
    fmt = "dur" if path.endswith(".dur") else "durg"
    _log.info(f"save  path={path}  fmt={fmt}  layers={len(doc.layers)}  frames={doc.frameCount}")
    payload = to_dur(doc) if fmt == "dur" else to_durg(doc)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    size = os.path.getsize(path)
    _log.info(f"save  ok  size={size:,}B")


def export_ansi(doc, path):
    """Exporta el compuesto del frame actual como archivo ANSI."""
    _log.info(f"export_ansi  path={path}")
    frame = doc.composite_frame()
    lines = []
    for row in range(frame.height):
        parts = []
        last_fg, last_bg = -1, -1
        for col in range(frame.width):
            ch     = frame.content[row][col]
            fg, bg = frame.newColorMap[row][col]
            if fg != last_fg or bg != last_bg:
                parts.append(_ansi_color_seq(fg, bg))
                last_fg, last_bg = fg, bg
            parts.append(ch)
        parts.append("\x1b[0m")
        lines.append("".join(parts))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))


# ── Motor de renderizado a imagen ─────────────────────────────────────────────
# Paleta ANSI estándar de 16 colores como tuplas RGB.
_ANSI_RGB = [
    (  0,   0,   0), (170,   0,   0), (  0, 170,   0), (170, 170,   0),
    (  0,   0, 170), (170,   0, 170), (  0, 170, 170), (170, 170, 170),
    ( 85,  85,  85), (255,  85,  85), ( 85, 255,  85), (255, 255,  85),
    ( 85,  85, 255), (255,  85, 255), ( 85, 255, 255), (255, 255, 255),
]

_CELL_W    = 8    # píxeles por celda (horizontal)
_CELL_H    = 16   # píxeles por celda (vertical)
_FONT_SIZE = 13

# Candidatos de fuente monoespacio en orden de preferencia (Arch/Linux)
_FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/Hack-Regular.ttf",
    "/usr/share/fonts/TTF/UbuntuMono-R.ttf",
    "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
]


def _load_font():
    """Carga la primera fuente TTF monoespacio disponible; fallback al bitmap de Pillow."""
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, _FONT_SIZE)
            except Exception:
                pass
    return ImageFont.load_default()


def _frame_to_pil(frame, font):
    """Convierte un frame compuesto en una imagen PIL.Image RGB."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (frame.width * _CELL_W, frame.height * _CELL_H))
    draw = ImageDraw.Draw(img)
    for row in range(frame.height):
        for col in range(frame.width):
            ch     = frame.content[row][col]
            fg, bg = frame.newColorMap[row][col]
            x0 = col * _CELL_W
            y0 = row * _CELL_H
            draw.rectangle(
                [x0, y0, x0 + _CELL_W - 1, y0 + _CELL_H - 1],
                fill=_ANSI_RGB[bg % 16],
            )
            if ch not in (" ", "\x00"):
                draw.text((x0, y0 + 1), ch, fill=_ANSI_RGB[fg % 16], font=font)
    return img


def _require_timeline(doc, fmt):
    """Lanza ValueError si el doc tiene menos de 2 frames (GIF/MP4 necesitan animación)."""
    if doc.frameCount < 2:
        raise ValueError(
            f"El documento necesita al menos 2 frames para exportar como {fmt}.\n"
            "Añade frames desde el menú Frame → Nuevo frame."
        )


# ── Exportación de imagen estática ────────────────────────────────────────────

def export_png(doc, path):
    """Exporta el frame actual como imagen PNG."""
    _log.info(f"export_png  path={path}")
    _frame_to_pil(doc.composite_frame(), _load_font()).save(path, "PNG")


def export_jpeg(doc, path, quality=90):
    """Exporta el frame actual como imagen JPEG."""
    _log.info(f"export_jpeg  path={path}  quality={quality}")
    _frame_to_pil(doc.composite_frame(), _load_font()).save(path, "JPEG", quality=quality)


# ── Exportación animada ────────────────────────────────────────────────────────

def export_gif(doc, path, frame_delay_ms=100):
    """Exporta todos los frames como GIF animado. Requiere al menos 2 frames."""
    _log.info(f"export_gif  path={path}  frames={doc.frameCount}  delay={frame_delay_ms}ms")
    _require_timeline(doc, "GIF")
    from PIL import Image
    font = _load_font()
    pil_frames = [_frame_to_pil(doc.composite_frame(i), font) for i in range(doc.frameCount)]
    # Paleta consistente: cuantizar con el primer frame como referencia
    p0 = pil_frames[0].quantize(colors=256)
    p_frames = [p0] + [f.quantize(colors=256, palette=p0) for f in pil_frames[1:]]
    p_frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=p_frames[1:],
        loop=0,
        duration=frame_delay_ms,
        optimize=False,
    )


def export_mp4(doc, path, fps=10):
    """Exporta todos los frames como vídeo MP4. Requiere al menos 2 frames e imageio+ffmpeg."""
    _log.info(f"export_mp4  path={path}  frames={doc.frameCount}  fps={fps}")
    _require_timeline(doc, "MP4")
    try:
        import imageio
        import numpy as np
    except ImportError as exc:
        raise ImportError(
            f"Faltan dependencias para exportar MP4 ({exc}).\n"
            "Instala con: pip install imageio[ffmpeg] numpy"
        ) from exc

    font   = _load_font()
    frames = [
        np.asarray(_frame_to_pil(doc.composite_frame(i), font))
        for i in range(doc.frameCount)
    ]
    with imageio.get_writer(path, fps=fps) as writer:
        for arr in frames:
            writer.append_data(arr)
