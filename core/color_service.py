def _build_palette_256():
    base = [
        "#000000", "#AA0000", "#00AA00", "#AA5500",
        "#0000AA", "#AA00AA", "#00AAAA", "#AAAAAA",
        "#555555", "#FF5555", "#55FF55", "#FFFF55",
        "#5555FF", "#FF55FF", "#55FFFF", "#FFFFFF",
    ]
    levels = [0, 95, 135, 175, 215, 255]
    cube = [f"#{r:02X}{g:02X}{b:02X}" for r in levels for g in levels for b in levels]
    grays = [f"#{v:02X}{v:02X}{v:02X}" for v in range(8, 248, 10)]
    return base + cube + grays


PALETTE_256 = _build_palette_256()
ANSI_COLORS = PALETTE_256[:16]


class ColorService:
    """Proveedor centralizado de paleta. Un solo punto para cambiar o extender colores."""

    def __init__(self, bus, mode="16"):
        self._bus = bus
        self._mode = mode
        self._palette = self._make(mode)

    def _make(self, mode):
        return list(PALETTE_256) if mode == "256" else list(ANSI_COLORS)

    def set_mode(self, mode):
        if mode == self._mode:
            return
        self._mode = mode
        self._palette = self._make(mode)
        self._bus.emit("color_mode_changed", {"mode": mode})

    def color(self, idx):
        """Hex del color en la paleta activa (hace wrap si el índice sale del rango)."""
        return self._palette[idx % len(self._palette)]

    def palette(self):
        return self._palette[:]

    def count(self):
        return len(self._palette)

    @property
    def mode(self):
        return self._mode
