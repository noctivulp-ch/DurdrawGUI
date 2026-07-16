"""
Modelo de documento con múltiples capas.

Todas las capas comparten el mismo conteo de frames (timeline global).
La composición se hace de abajo a arriba: celda vacía (space + bg=0) es
transparente.
"""

from copy import deepcopy
from core.movie import Movie


class _Opts:
    def __init__(self, w, h):
        self.sizeX = w
        self.sizeY = h


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

    def __init__(self, width, height):
        self.width  = width
        self.height = height
        self._frame_idx   = 0   # 0-based
        self._active_idx  = 0
        self._layers      = [Layer("Fondo", width, height)]

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
        """Funde todas las capas visibles. frame_idx=None → frame actual."""
        if frame_idx is None:
            frame_idx = self._frame_idx

        content  = [[" "] * self.width for _ in range(self.height)]
        colormap = [[[7, 0]] * self.width for _ in range(self.height)]

        for layer in self._layers:
            if not layer.visible:
                continue
            if frame_idx >= len(layer.frames):
                continue
            src = layer.frame_at(frame_idx)
            for r in range(self.height):
                for c in range(self.width):
                    ch = src.content[r][c]
                    fg, bg = src.newColorMap[r][c]
                    if ch != " " or bg != 0:
                        content[r][c]  = ch
                        colormap[r][c] = [fg, bg]

        return _CompositeFrame(content, colormap, self.width, self.height)

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

    def duplicate_current_frame(self):
        for layer in self._layers:
            layer.duplicate_frame(self._frame_idx)
        self._frame_idx += 1

    def delete_frame(self):
        if self.frameCount <= 1:
            return
        idx = self._frame_idx
        for layer in self._layers:
            layer.delete_frame(idx)
        self._frame_idx = min(idx, self.frameCount - 1)

    # ── Gestión de capas ──────────────────────────────────────────────────

    def add_layer(self, name=None):
        name = name or f"Capa {len(self._layers) + 1}"
        layer = Layer(name, self.width, self.height)
        # Añadir frames vacíos para igualar el conteo global
        for _ in range(self.frameCount - 1):
            layer.add_empty_frame()
        insert_at = self._active_idx + 1
        self._layers.insert(insert_at, layer)
        self._active_idx = insert_at

    def delete_active_layer(self):
        if len(self._layers) <= 1:
            return
        self._layers.pop(self._active_idx)
        self._active_idx = min(self._active_idx, len(self._layers) - 1)

    def set_active_layer(self, idx):
        self._active_idx = max(0, min(idx, len(self._layers) - 1))

    def move_layer(self, src_idx, dst_idx):
        dst_idx = max(0, min(dst_idx, len(self._layers) - 1))
        if src_idx == dst_idx:
            return
        layer = self._layers.pop(src_idx)
        self._layers.insert(dst_idx, layer)
        self._active_idx = dst_idx

    def _reset_layers(self, layers):
        """Reemplaza la lista de capas directamente. Solo para deserialización (core/io.py)."""
        self._layers      = layers
        self._active_idx  = 0
        self._frame_idx   = 0
