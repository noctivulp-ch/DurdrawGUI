from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QFrame, QLineEdit)
from PySide6.QtGui     import QColor, QPainter, QPen
from PySide6.QtCore    import Qt, QSize

from core.color_service import ANSI_COLORS, PALETTE_256, palette_cols


class _ColorSwatch(QPushButton):
    """Botón de color cuadrado con borde resaltable."""
    def __init__(self, idx: int, hex_color: str, parent=None):
        super().__init__(parent)
        self._idx = idx
        self._hex = hex_color
        self.setFixedSize(16, 16)
        self.setToolTip(f"#{idx}  {hex_color}")
        self.setStyleSheet(
            f"background-color:{hex_color}; border:1px solid #444; padding:0;"
        )

    def set_marks(self, is_fg: bool, is_bg: bool):
        """Resalta si este swatch es el color de frente/fondo activo (overlay
        de selección — ambos a la vez usan un color distintivo propio)."""
        if is_fg and is_bg:
            border, width = "#ff00ff", 2
        elif is_fg:
            border, width = "#ffffff", 2
        elif is_bg:
            border, width = "#ffff00", 2
        else:
            border, width = "#444444", 1
        self.setStyleSheet(
            f"background-color:{self._hex}; border:{width}px solid {border}; padding:0;"
        )


class _CharEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxLength(1)
        self.setFixedWidth(28)
        self.setText("@")


class ColorPanel(QWidget):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app
        self._swatches: list[_ColorSwatch] = []
        self._mode     = "16"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Carácter y colores activos ────────────────────────────────────
        top = QHBoxLayout()
        self._char_edit = _CharEdit()
        self._char_edit.textChanged.connect(self._on_char_changed)
        top.addWidget(QLabel("Ch:"))
        top.addWidget(self._char_edit)

        self._fg_swatch = _ColorSwatch(15, ANSI_COLORS[15])
        self._bg_swatch = _ColorSwatch(0,  ANSI_COLORS[0])
        self._fg_swatch.setToolTip("Color frontal (clic izq en paleta)")
        self._bg_swatch.setToolTip("Color de fondo (clic der en paleta)")
        top.addWidget(QLabel("FG:"))
        top.addWidget(self._fg_swatch)
        top.addWidget(QLabel("BG:"))
        top.addWidget(self._bg_swatch)
        top.addStretch()
        layout.addLayout(top)

        # ── Paleta ────────────────────────────────────────────────────────
        self._palette_frame = QWidget()
        layout.addWidget(self._palette_frame)
        layout.addStretch()

        self.rebuild_palette()

        # Escuchar cambios de color desde el bus
        app.bus.on("color_changed", self._on_color_changed)

    def rebuild_palette(self):
        for swatch in self._swatches:
            swatch.deleteLater()
        self._swatches.clear()

        old = self._palette_frame.layout()
        if old:
            QWidget().setLayout(old)   # desconectar layout viejo

        mode   = self.app.color_service.mode
        colors = ANSI_COLORS if mode == "16" else PALETTE_256
        cols   = palette_cols(mode)

        grid = QGridLayout()
        grid.setSpacing(1)
        grid.setContentsMargins(0, 0, 0, 0)
        self._palette_frame.setLayout(grid)

        for idx, hex_c in enumerate(colors):
            sw = _ColorSwatch(idx, hex_c)
            sw.clicked.connect(lambda _, i=idx: self.app.set_fg_color(i))
            sw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            sw.customContextMenuRequested.connect(
                lambda _, i=idx: self.app.set_bg_color(i)
            )
            r, c = divmod(idx, cols)
            grid.addWidget(sw, r, c)
            self._swatches.append(sw)

        self._mode = mode
        self._update_marks(self.app.fg_color, self.app.bg_color)

    def _update_marks(self, fg: int, bg: int):
        """Overlay de resaltado: marca en la grilla qué swatch(es) son el fg/bg activos."""
        for sw in self._swatches:
            sw.set_marks(sw._idx == fg, sw._idx == bg)

    def _on_color_changed(self, data: dict):
        fg   = data.get("fg", 15)
        bg   = data.get("bg", 0)
        ch   = data.get("char", "@")
        mode = self.app.color_service.mode

        colors = ANSI_COLORS if mode == "16" else PALETTE_256
        self._fg_swatch.setStyleSheet(
            f"background-color:{colors[fg]}; border:2px solid #ffffff; padding:0;"
        )
        self._bg_swatch.setStyleSheet(
            f"background-color:{colors[bg]}; border:2px solid #ffff00; padding:0;"
        )
        self._update_marks(fg, bg)
        if self._char_edit.text() != ch:
            self._char_edit.blockSignals(True)
            self._char_edit.setText(ch)
            self._char_edit.blockSignals(False)

    def _on_char_changed(self, text: str):
        if text:
            self.app.set_fg_char(text[-1])
