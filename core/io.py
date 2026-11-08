"""
Serialización, deserialización y exportación de documentos.

Responsabilidad única: traducir entre Document y representaciones externas
(.durg, .dur, ANSI). App.py delega aquí toda la lógica de archivo.
"""

import json
import gzip
import os

from core.document import Document, Layer
from core.color_service import PALETTE_256
import core.log as log
from core.raster import CharTable, TileCache, composite_codes

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


def _ansi_color_seq(fg, bg, color_format="16"):
    # En modo 256 emitimos SGR extendido (38;5 / 48;5) para no truncar la gama.
    if color_format == "256":
        return f"\x1b[38;5;{fg % 256}m\x1b[48;5;{bg % 256}m"
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
            "colorFormat": doc.color_format,
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
    # Compatibilidad con .dur legacy (durdraw v1–v6) que usan sizeX/sizeY.
    w = dm.get("columns", dm.get("sizeX"))
    h = dm.get("lines",   dm.get("sizeY"))
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
    color_fmt = str(dg.get("colorFormat", "16"))
    doc = Document(w, h, color_format=color_fmt)
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
    cfmt  = doc.color_format
    lines = []
    for row in range(frame.height):
        parts = []
        last_fg, last_bg = -1, -1
        for col in range(frame.width):
            ch     = frame.content[row][col]
            fg, bg = frame.newColorMap[row][col]
            if fg != last_fg or bg != last_bg:
                parts.append(_ansi_color_seq(fg, bg, cfmt))
                last_fg, last_bg = fg, bg
            parts.append(ch)
        parts.append("\x1b[0m")
        lines.append("".join(parts))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))


# ── Motor de renderizado a imagen ─────────────────────────────────────────────
def _hex_to_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# Paleta RGB completa de 256 colores (misma que ColorService.PALETTE_256).
# Los primeros 16 son la paleta ANSI estándar; el resto la rampa 6×6×6 + grises.
_RGB_256 = [_hex_to_rgb(c) for c in PALETTE_256]


def _palette_rgb(idx, color_format):
    """RGB de un índice de color respetando el formato (16 o 256)."""
    if color_format == "256":
        return _RGB_256[idx % len(_RGB_256)]
    return _RGB_256[idx % 16]


_CELL_W    = 8    # píxeles por celda (horizontal)
_CELL_H    = 16   # píxeles por celda (vertical)
_FONT_SIZE = 13

# Familia de fuente preferida para exportación (la fija App desde AppConfig).
_EXPORT_FONT_FAMILY = None

# Candidatos de fuente monoespacio en orden de preferencia (Arch/Linux)
_FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/Hack-Regular.ttf",
    "/usr/share/fonts/TTF/UbuntuMono-R.ttf",
    "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
]


def set_export_font_family(name):
    """Fija la familia de fuente usada al exportar imágenes (coincide con el canvas)."""
    global _EXPORT_FONT_FAMILY
    _EXPORT_FONT_FAMILY = name or None


def _resolve_font_file(family):
    """Resuelve una familia (ej. 'Hack') al archivo TTF real vía fontconfig."""
    if not family:
        return None
    try:
        import subprocess
        out = subprocess.run(
            ["fc-match", "--format=%{file}", family],
            capture_output=True, text=True, timeout=2,
        )
        path = out.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def _load_font():
    """Carga la fuente preferida del usuario; luego candidatos; fallback bitmap de Pillow."""
    from PIL import ImageFont
    resolved = _resolve_font_file(_EXPORT_FONT_FAMILY)
    for path in [p for p in (resolved,) if p] + _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, _FONT_SIZE)
            except Exception:
                pass
    return ImageFont.load_default()


_GLYPH_MASKS: dict = {}   # (id(font), carácter) → cobertura uint8 (_CELL_H, 1 + _CELL_W)


def _glyph_mask(font, ch):
    """Cobertura del carácter tal como lo deja draw.text() en una celda.

    PIL rasterizaba el glifo en cada celda de cada frame (el 80 % de exportar un
    GIF). Se dibuja una vez por carácter y fuente (ADR 0002). La columna 0 es lo
    que el glifo desborda a la izquierda: hasta 1 px en DejaVu Sans Mono a 13 px
    (los bloques y las líneas de caja), que caía sobre la celda anterior."""
    key = (id(font), ch)
    m = _GLYPH_MASKS.get(key)
    if m is None:
        import numpy as np
        from PIL import Image, ImageDraw
        img = Image.new("L", (1 + _CELL_W, _CELL_H), 0)
        if ch not in (" ", "\x00", ""):
            ImageDraw.Draw(img).text((1, 1), ch, fill=255, font=font)
        m = _GLYPH_MASKS[key] = np.asarray(img, dtype=np.uint8)
    return m


def _pil_blend(dst, src, cov):
    """BLEND + DIV255 de Pillow: dst·(255−cov) + src·cov, redondeado."""
    v = dst * (255 - cov) + src * cov + 128
    return ((v >> 8) + v) >> 8


def _pack(rgb):
    """(…, 3) int → uint32 0xFFRRGGBB."""
    return (0xFF000000 | (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]).astype("uint32")


def _unpack(px):
    import numpy as np
    px = px.astype(np.int64)
    return np.stack([(px >> 16) & 0xFF, (px >> 8) & 0xFF, px & 0xFF], axis=-1)


def _render_tiles_pil(mask_idx, fg, bg, masks, pal):
    """Baldosas de n celdas como las deja ImageDraw: rectángulo de fondo y
    draw.text encima, con la mezcla de Pillow en los píxeles con antialiasing.
    pal: (colores, 3) int. Devuelve uint32 0xFFRRGGBB."""
    import numpy as np
    cov = masks[mask_idx]                                          # (n, ch, cw) int
    tfg, tbg = pal[fg], pal[bg]
    out = np.where((cov >= 128)[..., None], tfg[:, None, None, :], tbg[:, None, None, :])
    part = (cov > 0) & (cov < 255)
    if part.any():
        n_idx = np.nonzero(part)[0]
        a = cov[part][:, None]
        out[part] = _pil_blend(tbg[n_idx], tfg[n_idx], a)
    return _pack(out)


class _PilRaster:
    """Estado de una exportación: tabla de caracteres, máscaras y baldosas que
    se reaprovechan de un frame al siguiente (ADR 0002)."""

    def __init__(self, font, color_format):
        import numpy as np
        self.font = font
        self.table = CharTable()
        self.pal = np.array(_RGB_256 if color_format == "256" else _RGB_256[:16], dtype=np.int64)
        self.tiles = TileCache(_render_tiles_pil)
        self._masks = None

    def masks(self):
        import numpy as np
        chars = self.table.chars
        if self._masks is None or len(self._masks) < len(chars):
            self._masks = np.stack([_glyph_mask(self.font, ch) for ch in chars]).astype(np.int64)
        return self._masks

    def image(self, codes, fg, bg):
        """PIL.Image RGB. Mismos píxeles que dibujar celda a celda con
        ImageDraw, incluido el píxel que un glifo desborda sobre la celda de su
        izquierda (tests/test_raster.py)."""
        import numpy as np
        from PIL import Image
        h, w = codes.shape
        m = self.masks()
        fg = fg % len(self.pal)
        img = self.tiles.image(codes, fg, bg, np.ascontiguousarray(m[:, :, 1:]), self.pal)
        # Desborde a la izquierda: la celda c pinta su texto después que la c−1.
        if w > 1:
            over = m[codes[:, 1:], :, 0]                            # (h, w−1, ch)
            r, c, y = np.nonzero(over)
            if len(r):
                ys, px = r * _CELL_H + y, c * _CELL_W + _CELL_W - 1
                a = over[r, c, y][:, None]
                img[ys, px] = _pack(_pil_blend(_unpack(img[ys, px]), self.pal[fg[r, c + 1]], a))
        return Image.frombuffer("RGB", (w * _CELL_W, h * _CELL_H), img, "raw", "BGRX", 0, 1)


def _frame_to_pil(frame, font, color_format="16"):
    """Convierte un frame compuesto (content + newColorMap) en una imagen RGB."""
    import numpy as np
    r = _PilRaster(font, color_format)
    codes = np.array([[r.table.code(ch) for ch in row] for row in frame.content], dtype=np.int64)
    pairs = np.array([[p[:2] for p in row] for row in frame.newColorMap], dtype=np.int64)
    return r.image(codes, pairs[..., 0], pairs[..., 1])


def _doc_frames_pil(doc, font, color_format):
    """Imágenes RGB de todos los frames compuestos, sin pasar por listas."""
    r = _PilRaster(font, color_format)
    for i in range(doc.frameCount):
        codes, fg, bg = composite_codes(doc, i, r.table)
        yield r.image(codes, fg, bg)


def _gif_palette_image(color_format):
    """Imagen 'P' de Pillow con la paleta exacta del documento para cuantizar GIF."""
    from PIL import Image
    colors = _RGB_256 if color_format == "256" else _RGB_256[:16]
    flat = []
    for (r, g, b) in colors:
        flat += [r, g, b]
    flat += [0, 0, 0] * (256 - len(colors))   # Pillow exige 256 entradas
    pimg = Image.new("P", (1, 1))
    pimg.putpalette(flat)
    return pimg


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
    _frame_to_pil(doc.composite_frame(), _load_font(), doc.color_format).save(path, "PNG")


def export_jpeg(doc, path, quality=90):
    """Exporta el frame actual como imagen JPEG."""
    _log.info(f"export_jpeg  path={path}  quality={quality}")
    _frame_to_pil(doc.composite_frame(), _load_font(), doc.color_format).save(path, "JPEG", quality=quality)


# ── Exportación animada ────────────────────────────────────────────────────────

def export_gif(doc, path, frame_delay_ms=100):
    """Exporta todos los frames como GIF animado. Requiere al menos 2 frames."""
    _log.info(f"export_gif  path={path}  frames={doc.frameCount}  delay={frame_delay_ms}ms")
    _require_timeline(doc, "GIF")
    from PIL import Image
    font = _load_font()
    cfmt = doc.color_format
    pil_frames = list(_doc_frames_pil(doc, font, cfmt))
    # Paleta EXACTA a partir de la paleta conocida del documento (≤256 colores).
    # Cuantizar contra ella (sin dithering) mapea cada píxel a su color real en
    # todos los frames, evitando la distorsión de fijar la paleta al frame 0.
    master = _gif_palette_image(cfmt)
    p_frames = [f.quantize(palette=master, dither=Image.Dither.NONE) for f in pil_frames]
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
    cfmt   = doc.color_format
    frames = [np.asarray(img) for img in _doc_frames_pil(doc, font, cfmt)]
    # H.264 exige dimensiones pares. Con las celdas actuales (8×16) el tamaño ya
    # es par, pero rellenamos 1px por si el tamaño de celda cambia en el futuro.
    def _pad_even(arr):
        h, w = arr.shape[:2]
        pad_h, pad_w = h % 2, w % 2
        if pad_h or pad_w:
            arr = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
        return arr

    with imageio.get_writer(path, fps=fps) as writer:
        for arr in frames:
            writer.append_data(_pad_even(arr))
