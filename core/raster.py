"""Rasterizado vectorizado del lienzo: de capas a píxeles sin bucles por celda.

Por qué existe y qué se midió: docs/decisiones/0002-raster-numpy.md.

Tres piezas, ninguna sabe de Qt:

- CharTable: carácter ↔ código entero. Los códigos son estables durante toda la
  sesión (no dependen de la fuente ni del zoom), así que las matrices de un
  frame sobreviven a un cambio de zoom.
- composite_codes(): funde las capas visibles de un frame en tres matrices
  (código, fg, bg). Misma regla que Document.composite_frame(): una celda con
  espacio y bg=0 es transparente.
- rasterize(): con un atlas de coberturas de glifo (una por carácter, del
  tamaño de la celda en píxeles), produce la imagen ARGB32 del bloque de celdas.
"""

from __future__ import annotations

import numpy as np

EMPTY_CHARS = (" ", "\x00", "")


class CharTable:
    """Diccionario creciente carácter → código. El código 0 es el espacio."""

    def __init__(self):
        self.chars: list[str] = [" "]
        self.codes: dict[str, int] = {" ": 0}

    def code(self, ch: str) -> int:
        c = self.codes.get(ch)
        if c is None:
            c = self.codes[ch] = len(self.chars)
            self.chars.append(ch)
        return c

    def __len__(self):
        return len(self.chars)


def composite_codes(doc, frame_idx: int, table: CharTable):
    """(códigos, fg, bg) del frame compuesto, como matrices int32 (alto, ancho).

    Se resuelve de arriba abajo: cada celda se queda con la primera capa opaca y
    deja de mirar las de debajo. Con 10 capas es la mitad de trabajo que fundir
    de abajo arriba (medido: docs/pendientes/rust-modulos.md)."""
    w, h = doc.width, doc.height
    srcs = [layer.frame_at(frame_idx) for layer in reversed(doc.layers)
            if layer.visible and frame_idx < len(layer.frames)]
    codes_get = table.codes.get
    codes: list[int] = []
    fgs: list[int] = []
    bgs: list[int] = []
    add_c, add_f, add_b = codes.append, fgs.append, bgs.append
    for r in range(h):
        rows = [(s.content[r], s.newColorMap[r]) for s in srcs]
        for c in range(w):
            for crow, mrow in rows:
                ch = crow[c]
                p = mrow[c]
                if ch != " " or p[1]:
                    k = codes_get(ch)
                    if k is None:
                        k = table.code(ch)
                    add_c(k); add_f(p[0]); add_b(p[1])
                    break
            else:
                add_c(0); add_f(7); add_b(0)
    shape = (h, w)
    return (np.array(codes, dtype=np.int32).reshape(shape),
            np.array(fgs, dtype=np.int32).reshape(shape),
            np.array(bgs, dtype=np.int32).reshape(shape))


def palette_argb(hex_colors) -> np.ndarray:
    """Paleta '#rrggbb' → uint32 0xFFRRGGBB (el formato de QImage.Format_RGB32)."""
    out = np.empty(len(hex_colors), dtype=np.uint32)
    for i, hx in enumerate(hex_colors):
        out[i] = 0xFF000000 | int(hx.lstrip("#")[:6], 16)
    return out


def _byte_mul(x, a):
    """x·a/255 en los cuatro canales de un ARGB32, con el redondeo de Qt
    (BYTE_MUL en qdrawhelper_p.h)."""
    m = np.uint64(0x00FF00FF)
    r = np.uint64(0x00800080)
    e = np.uint64(8)
    t = (x & m) * a
    t = ((t + ((t >> e) & m) + r) >> e) & m
    u = ((x >> e) & m) * a
    u = (u + ((u >> e) & m) + r) & np.uint64(0xFF00FF00)
    return u | t


def _blend_coverage(fg, a, bg):
    """Frente fg sobre fondo bg con cobertura a (0..255), como QPainter pinta
    un glifo con antialiasing sobre un píxel opaco: s = fg·a; s + bg·(255−alfa(s))."""
    fg = fg.astype(np.uint64)
    bg = bg.astype(np.uint64)
    a = a.astype(np.uint64)
    s = _byte_mul(fg, a)
    return (s + _byte_mul(bg, np.uint64(255) - (s >> np.uint64(24)))).astype(np.uint32)


def render_tiles(mask_idx: np.ndarray, fg: np.ndarray, bg: np.ndarray,
                 masks: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Baldosas (n, alto_celda, ancho_celda) uint32 de n celdas sueltas.

    masks: (n_máscaras, alto_celda, ancho_celda) uint8, cobertura del glifo
    (0 = fondo, 255 = frente). Los valores intermedios son el antialiasing del
    texto y se mezclan como lo hace QPainter. fg y bg ya vienen en rango."""
    fgc = pal[fg][:, None, None]
    bgc = pal[bg][:, None, None]
    cov = masks[mask_idx]
    out = np.where(cov >= 128, fgc, bgc)
    partial = (cov > 0) & (cov < 255)
    if partial.any():
        shape = cov.shape
        out[partial] = _blend_coverage(np.broadcast_to(fgc, shape)[partial], cov[partial],
                                       np.broadcast_to(bgc, shape)[partial])
    return out


def unique_cells(mask_idx, fg, bg):
    """Clave entera por combinación (máscara, fg, bg): (claves únicas, inversa)."""
    keys = (mask_idx.astype(np.int64) << 20) | (fg.astype(np.int64) << 10) | bg
    return np.unique(keys.ravel(), return_inverse=True)


class TileCache:
    """Baldosas ya pintadas por combinación (máscara, fg, bg).

    Un frame tiene muchas menos combinaciones distintas que celdas, y se
    repiten de un frame al siguiente: pintar cada una una vez y luego copiarla
    deja el coste del repintado en un gather de memoria, independiente de
    cuánto texto con antialiasing haya (ADR 0002). Quien la usa llama a
    clear() cuando cambian la paleta o el atlas."""

    def __init__(self, render=None):
        """render(mask_idx, fg, bg, masks, pal) → (n, alto, ancho) uint32: pinta
        n baldosas. Por defecto render_tiles (la mezcla de QPainter)."""
        self._render = render or render_tiles
        self.clear()

    def clear(self):
        self.keys = np.zeros(0, dtype=np.int64)     # ordenadas
        self.slots = np.zeros(0, dtype=np.int64)    # baldosa de cada clave
        self.tiles = None
        self.count = 0

    def image(self, mask_idx, fg, bg, masks, pal) -> np.ndarray:
        if self.tiles is not None and self.tiles.shape[1:] != masks.shape[1:]:
            self.clear()
        n = len(pal)
        fg = fg % n
        bg = bg % n
        uk, inv = unique_cells(mask_idx, fg, bg)
        pos = np.searchsorted(self.keys, uk)
        found = np.zeros(len(uk), dtype=bool)
        inside = pos < len(self.keys)
        found[inside] = self.keys[pos[inside]] == uk[inside]
        slot = np.empty(len(uk), dtype=np.int64)
        slot[found] = self.slots[pos[found]]
        if not found.all():
            new = uk[~found]
            tiles = self._render((new >> 20).astype(np.int64), (new >> 10) & 0x3FF,
                                 new & 0x3FF, masks, pal)
            first = self._append(tiles)
            new_slots = np.arange(first, first + len(new))
            slot[~found] = new_slots
            keys = np.concatenate([self.keys, new])
            slots = np.concatenate([self.slots, new_slots])
            order = np.argsort(keys, kind="stable")
            self.keys, self.slots = keys[order], slots[order]
        cells = self.tiles[slot[inv].reshape(mask_idx.shape)]        # (filas, cols, ch, cw)
        rows, cols, ch, cw = cells.shape
        return np.ascontiguousarray(cells.transpose(0, 2, 1, 3)).reshape(rows * ch, cols * cw)

    def _append(self, tiles):
        m = len(tiles)
        if self.tiles is None:
            self.tiles = np.empty((max(256, m * 2),) + tiles.shape[1:], dtype=np.uint32)
        elif self.count + m > len(self.tiles):
            grown = np.empty((max(len(self.tiles) * 2, self.count + m),) + tiles.shape[1:],
                             dtype=np.uint32)
            grown[:self.count] = self.tiles[:self.count]
            self.tiles = grown
        first = self.count
        self.tiles[first:first + m] = tiles
        self.count += m
        return first


def rasterize(mask_idx: np.ndarray, fg: np.ndarray, bg: np.ndarray,
              masks: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Imagen uint32 (filas·alto_celda, cols·ancho_celda) de un bloque de celdas,
    sin caché (para pruebas y para el banco). fg y bg hacen módulo la paleta,
    igual que ColorService.color()."""
    n = len(pal)
    return TileCache().image(mask_idx, fg % n, bg % n, masks, pal)
