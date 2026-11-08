"""
Modelo de documento con múltiples capas.

Todas las capas comparten el mismo conteo de frames (timeline global).
La composición se hace de abajo a arriba: celda vacía (space + bg=0) es
transparente.
"""

from copy import deepcopy
from core.movie import Movie
import core.log as log

_log = log.get("doc")


class _Opts:
    def __init__(self, w, h):
        self.sizeX = w
        self.sizeY = h


_EMPTY_PAIR = [7, 0]   # compartido por todas las celdas vacías del compuesto


class _CompositeFrame:
    """Frame virtual resultado de fundir capas. Solo lectura (no pertenece a ninguna capa)."""
    __slots__ = ("content", "newColorMap", "width", "height")

    def __init__(self, content, colormap, width, height):
        self.content     = content
        self.newColorMap = colormap
        self.width       = width
        self.height      = height


class Layer:
    """Capa de animación: un Movie de durdraw como almacén de frames."""

    def __init__(self, name, width, height):
        self.name    = name
        self.visible = True
        self._movie  = Movie(_Opts(width, height))

    # ── Propiedades ───────────────────────────────────────────────────────

    @property
    def frames(self):
        return self._movie.frames

    @property
    def width(self):
        return self._movie.sizeX

    @property
    def height(self):
        return self._movie.sizeY

    def frame_at(self, idx):
        return self._movie.frames[idx]

    # ── Gestión de frames ─────────────────────────────────────────────────

    def add_empty_frame(self):
        self._movie.addEmptyFrame()

    def duplicate_frame(self, idx):
        """Duplica el frame en idx e inserta la copia inmediatamente después."""
        self._movie.gotoFrame(idx + 1)
        self._movie.duplicateCurrentFrame()

    def delete_frame(self, idx):
        if len(self._movie.frames) <= 1:
            return
        self._movie.gotoFrame(idx + 1)
        self._movie.deleteFrame()


class Document:
    """Documento activo: lista de capas sincronizadas en frames y composición."""

    def __init__(self, width, height, color_format="16"):
        self.width        = width
        self.height       = height
        self.color_format = color_format   # "16" o "256"
        self._frame_idx   = 0   # 0-based
        self._active_idx  = 0
        self._layers      = [Layer("Fondo", width, height)]
        _log.debug(f"Document({width}×{height}  color={color_format})")

    # ── Compat con Movie (app.py usa estas props) ─────────────────────────

    @property
    def frameCount(self):
        return len(self._layers[0].frames) if self._layers else 0

    @property
    def currentFrameNumber(self):
        return self._frame_idx + 1  # 1-based

    @property
    def sizeX(self):
        return self.width

    @property
    def sizeY(self):
        return self.height

    # ── Acceso a capas ────────────────────────────────────────────────────

    @property
    def layers(self):
        return self._layers

    @property
    def active_layer(self):
        return self._layers[self._active_idx]

    @property
    def active_layer_idx(self):
        return self._active_idx

    @property
    def current_frame_idx(self):
        return self._frame_idx

    # ── Acceso al frame activo ────────────────────────────────────────────

    def current_frame(self):
        """Frame de la capa activa en la posición temporal actual."""
        return self._layers[self._active_idx].frame_at(self._frame_idx)

    # ── Composición ───────────────────────────────────────────────────────

    def composite_frame(self, frame_idx=None):
        """Funde todas las capas visibles. frame_idx=None → frame actual.

        Se resuelve de arriba abajo: cada celda se queda con la primera capa
        opaca y no mira las de debajo (la mitad de trabajo con 10 capas). Los
        pares [fg, bg] del resultado son los de las capas, sin copiar: crear
        16 080 listas por frame disparaba el recolector de basura sobre todo el
        documento. Solo lectura. Cifras en docs/pendientes/rust-modulos.md."""
        if frame_idx is None:
            frame_idx = self._frame_idx
        w = self.width
        srcs = [layer.frame_at(frame_idx) for layer in reversed(self._layers)
                if layer.visible and frame_idx < len(layer.frames)]
        content, colormap = [], []
        for r in range(self.height):
            rows = [(s.content[r], s.newColorMap[r]) for s in srcs]
            out_c = [" "] * w
            out_m = [None] * w
            for c in range(w):
                for crow, mrow in rows:
                    ch = crow[c]
                    p = mrow[c]
                    if ch != " " or p[1] != 0:
                        out_c[c] = ch
                        out_m[c] = p   # compartido: los pares no se mutan (core/grid_copy.py)
                        break
                else:
                    out_m[c] = _EMPTY_PAIR
            content.append(out_c)
            colormap.append(out_m)
        return _CompositeFrame(content, colormap, self.width, self.height)

    def has_extended_colors(self) -> bool:
        """True si alguna celda, de cualquier capa/frame, usa fg/bg fuera de 0-15
        (paleta extendida de 256). Usado para bloquear la conversión a 16 colores."""
        for layer in self._layers:
            for frame in layer.frames:
                for row in frame.newColorMap:
                    for fg, bg in row:
                        if fg > 15 or bg > 15:
                            return True
        return False

    def composite_cell(self, col, row):
        """(ch, fg, bg) compuesto en la celda dada para el frame actual."""
        ch, fg, bg = " ", 7, 0
        for layer in self._layers:
            if not layer.visible:
                continue
            if self._frame_idx >= len(layer.frames):
                continue
            src = layer.frame_at(self._frame_idx)
            if not (0 <= row < src.height and 0 <= col < src.width):
                continue
            l_ch = src.content[row][col]
            l_fg, l_bg = src.newColorMap[row][col]
            if l_ch != " " or l_bg != 0:
                ch, fg, bg = l_ch, l_fg, l_bg
        return ch, fg, bg

    # ── Gestión de frames (aplica a todas las capas) ──────────────────────

    def goto_frame(self, n):
        """n es 1-based."""
        self._frame_idx = max(0, min(n - 1, self.frameCount - 1))

    def next_frame(self):
        if self._frame_idx < self.frameCount - 1:
            self._frame_idx += 1

    def add_empty_frame(self):
        for layer in self._layers:
            layer.add_empty_frame()
        self._frame_idx = self.frameCount - 1
        _log.debug(f"add_empty_frame  total={self.frameCount}")

    def duplicate_current_frame(self):
        for layer in self._layers:
            layer.duplicate_frame(self._frame_idx)
        self._frame_idx += 1
        _log.debug(f"duplicate_frame  idx={self._frame_idx}  total={self.frameCount}")

    def delete_frame(self):
        if self.frameCount <= 1:
            return
        idx = self._frame_idx
        for layer in self._layers:
            layer.delete_frame(idx)
        self._frame_idx = min(idx, self.frameCount - 1)
        _log.debug(f"delete_frame  idx={idx}  total={self.frameCount}")

    # ── Gestión de capas ──────────────────────────────────────────────────

    def add_layer(self, name=None):
        name = name or f"Capa {len(self._layers) + 1}"
        layer = Layer(name, self.width, self.height)
        for _ in range(self.frameCount - 1):
            layer.add_empty_frame()
        insert_at = self._active_idx + 1
        self._layers.insert(insert_at, layer)
        self._active_idx = insert_at
        _log.debug(f"add_layer  name='{name}'  idx={insert_at}  total={len(self._layers)}")

    def delete_active_layer(self):
        if len(self._layers) <= 1:
            return
        name = self._layers[self._active_idx].name
        self._layers.pop(self._active_idx)
        self._active_idx = min(self._active_idx, len(self._layers) - 1)
        _log.debug(f"delete_layer  name='{name}'  total={len(self._layers)}")

    def set_active_layer(self, idx):
        old = self._active_idx
        self._active_idx = max(0, min(idx, len(self._layers) - 1))
        if old != self._active_idx:
            _log.debug(f"set_active_layer  {old}→{self._active_idx}  name='{self.active_layer.name}'")

    def move_layer(self, src_idx, dst_idx):
        dst_idx = max(0, min(dst_idx, len(self._layers) - 1))
        if src_idx == dst_idx:
            return
        layer = self._layers.pop(src_idx)
        self._layers.insert(dst_idx, layer)
        self._active_idx = dst_idx
        _log.debug(f"move_layer  {src_idx}→{dst_idx}  name='{layer.name}'")

    def _reset_layers(self, layers):
        """Reemplaza la lista de capas directamente. Solo para deserialización (core/io.py)."""
        self._layers      = layers
        self._active_idx  = 0
        self._frame_idx   = 0
        _log.debug(f"_reset_layers  n={len(layers)}")
