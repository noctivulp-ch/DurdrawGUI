"""Panel selector de caracteres — grupos con scroll y pestañas de doble fila."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea,
    QGridLayout, QToolButton, QLabel, QSizePolicy,
    QStackedWidget, QPushButton, QButtonGroup,
)
from PySide6.QtGui  import QFont
from PySide6.QtCore import Qt, QSize, Signal

# ── Grupos de caracteres ──────────────────────────────────────────────────────

GROUPS: dict[str, list[str]] = {
    "ASCII": [chr(i) for i in range(32, 127)],

    "Cajas": list(
        # simples
        "─│┌┐└┘├┤┬┴┼"
        # gruesas
        "━┃┏┓┗┛┣┫┳┻╋"
        # dobles
        "═║╔╗╚╝╠╣╦╩╬"
        # mixtas simple/doble
        "╒╓╕╖╘╙╛╜╞╟╡╢╤╥╧╨╫╪"
        # medias líneas
        "╴╵╶╷╸╹╺╻╼╽╾╿"
        # redondas
        "╭╮╰╯╌╍╎╏┄┅┆┇┈┉┊┋"
    ),

    "Bloques": list(
        # bloques de octavos verticales
        "▁▂▃▄▅▆▇█"
        # bloques horizontales
        "▏▎▍▌▋▊▉"
        # medios
        "▀▄▌▐"
        # cuadrantes
        "▖▗▘▙▚▛▜▝▞▟"
        # tramados
        "░▒▓"
        # geométricos
        "■□▢▣▤▥▦▧▨▩▪▫▬▭▮▯"
        "◆◇◈◉◊○◌◍◎●◐◑◒◓◔◕"
        "◘◙◚◛◜◝◞◟◠◡◢◣◤◥◦◧◨◩◪◫◬◭◮◯"
    ),

    "Flechas": list(
        "←→↑↓↖↗↘↙↔↕↵↩↪↫↬↭↮↯"
        "⇐⇒⇑⇓⇔⇕⇖⇗⇘⇙"
        "➔➕➖➗➘➙➚➛➜➝➞➟➠➡"
        "▲▴△▵▶▸▷▹►▻▼▾▽▿◀◂◁◃◄◅"
    ),

    "Símbolos": list(
        # musicales / caras
        "☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨"
        # matemáticos
        "±×÷°µ∞≈≠≤≥√∑∏∂∫≡⊕⊗"
        # griegos útiles
        "αβγδεζηθλμπρσφψωΩΔΘΛΞΠΣΦΨ"
        # moneda / puntuación extra
        "©®™€£¥¢¿¡§¶†‡…·"
        # extra
        "★☆✓✗✦✧✩✪✫✬✭✮✯✰"
    ),
}

_BTN_W   = 35   # ancho mínimo por botón de carácter (px)
_BTN_H   = 35   # altura fija
_SPACING = 1    # espaciado entre botones
_MARGIN  = 2    # margen interior del grid


def _btn_label(ch: str) -> str:
    if ch == ' ':
        return '·'
    if ch == '&':
        return '&&'
    return ch


# ── Barra de pestañas con wrap automático ─────────────────────────────────────

class _FlowTabBar(QWidget):
    """
    Barra de pestañas que envuelve a una segunda fila cuando el ancho no alcanza.
    Usa posicionamiento manual (setGeometry) en lugar de layouts para controlar
    exactamente cuántas caben por fila.
    """
    tab_changed = Signal(int)

    _H   = 24   # altura de cada botón-pestaña
    _MIN = 75   # ancho mínimo por pestaña — suficiente para "Símbolos" sin cortar
    _GAP = 1    # separación entre pestañas

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self._btns: list[QPushButton] = []
        self._grp = QButtonGroup(self)
        self._grp.setExclusive(True)
        for i, lbl in enumerate(labels):
            btn = QPushButton(lbl, self)
            btn.setCheckable(True)
            btn.setFixedHeight(self._H)
            btn.toggled.connect(
                lambda on, idx=i: self.tab_changed.emit(idx) if on else None
            )
            self._grp.addButton(btn, i)
            self._btns.append(btn)
        if self._btns:
            self._btns[0].setChecked(True)

    def set_checked(self, idx: int):
        if 0 <= idx < len(self._btns):
            self._btns[idx].setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout(event.size().width())

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout(self.width())

    def _relayout(self, w: int):
        if w < 1 or not self._btns:
            return
        n       = len(self._btns)
        per_row = max(1, w // (self._MIN + self._GAP))
        per_row = min(per_row, n)
        btn_w   = (w - (per_row - 1) * self._GAP) // per_row

        x = y = 0
        for i, btn in enumerate(self._btns):
            if i > 0 and i % per_row == 0:
                x  = 0
                y += self._H + self._GAP
            btn.setGeometry(x, y, btn_w, self._H)
            x += btn_w + self._GAP

        self.setFixedHeight(y + self._H)


# ── Rejilla de caracteres ─────────────────────────────────────────────────────

class _CharGrid(QWidget):
    """Rejilla de botones que recalcula columnas al redimensionarse."""

    def __init__(self, chars: list[str], app, parent=None):
        super().__init__(parent)
        self._app          = app
        self._chars        = chars
        self._cols         = 0
        self._needs_layout = True
        self._buttons: list[QToolButton] = []
        self._marked_char: str | None = None
        self._marked_row:  int | None = None

        font = QFont("Monospace", 12)
        font.setFixedPitch(True)

        self._grid = QGridLayout(self)
        self._grid.setSpacing(_SPACING)
        self._grid.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        for ch in chars:
            btn = QToolButton()
            btn.setText(_btn_label(ch))
            btn.setFont(font)
            btn.setFixedHeight(_BTN_H)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setToolTip(f"U+{ord(ch):04X}  {ch}")
            btn.clicked.connect(lambda _, c=ch: self._pick(c))
            self._buttons.append(btn)

    def minimumSizeHint(self) -> QSize:
        return QSize(_BTN_W + 2 * _MARGIN, _BTN_H + 2 * _MARGIN)

    def paintEvent(self, event):
        if self._needs_layout:
            w = self.width()
            if w >= _BTN_W:
                cols = max(1, (w - 2 * _MARGIN + _SPACING) // (_BTN_W + _SPACING))
                cols = min(cols, len(self._chars))
                self._relayout(cols)
                self._needs_layout = False
                self.update()
                return
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._needs_layout:
            return
        w = event.size().width()
        if w < _BTN_W:
            return
        cols = max(1, (w - 2 * _MARGIN + _SPACING) // (_BTN_W + _SPACING))
        cols = min(cols, len(self._chars))
        if cols != self._cols:
            self._relayout(cols)

    def _relayout(self, cols: int):
        while self._grid.count():
            self._grid.takeAt(0)
        for c in range(max(self._cols, cols) + 1):
            self._grid.setColumnStretch(c, 0)
        self._cols = cols
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        for idx, btn in enumerate(self._buttons):
            r, c = divmod(idx, cols)
            self._grid.addWidget(btn, r, c)
        self.updateGeometry()

    def _pick(self, ch: str):
        self._app.set_fg_char(ch)
        self._app.bus.emit("color_changed", {
            "fg": self._app.fg_color,
            "bg": self._app.bg_color,
            "char": ch,
        })

    # ── Overlays de resaltado (carácter activo / fila de navegación) ───────

    def mark_active_char(self, ch: str | None):
        self._marked_char = ch
        self._restyle_buttons()

    def mark_row(self, row: int | None):
        self._marked_row = row
        self._restyle_buttons()

    def _restyle_buttons(self):
        for idx, btn in enumerate(self._buttons):
            is_active = self._chars[idx] == self._marked_char
            in_row    = self._marked_row is not None and idx // 10 == self._marked_row
            if is_active:
                btn.setStyleSheet("QToolButton{border:2px solid #ffffff; background-color:#3a3a3a;}")
            elif in_row:
                btn.setStyleSheet("QToolButton{border:1px solid #55aaff; background-color:#2a2a3a;}")
            else:
                btn.setStyleSheet("")


# ── Panel principal ───────────────────────────────────────────────────────────

class CharPanel(QWidget):
    """Selector de caracteres con pestañas de wrap automático."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self._app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(0)

        lbl = QLabel("Caracteres")
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lbl.setStyleSheet("font-size:10px; color:#888; padding:0 4px;")
        layout.addWidget(lbl)

        labels = list(GROUPS.keys())
        self._tab_bar = _FlowTabBar(labels)
        layout.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        self._grids: list[_CharGrid] = []
        for chars in GROUPS.values():
            grid_widget = _CharGrid(chars, app)
            self._grids.append(grid_widget)
            scroll = QScrollArea()
            scroll.setWidget(grid_widget)
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(60)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._stack.addWidget(scroll)

        self._tab_bar.tab_changed.connect(self._stack.setCurrentIndex)
        layout.addWidget(self._stack, stretch=1)

        app.bus.on("color_changed", self._on_color_changed)

    def _on_color_changed(self, data: dict):
        ch = data.get("char")
        for grid in self._grids:
            grid.mark_active_char(ch)

    # ── API de navegación por teclado (AsciiCanvas en modo cursor) ─────────

    def group_names(self) -> list[str]:
        return list(GROUPS.keys())

    def current_group_index(self) -> int:
        return self._stack.currentIndex()

    def group_chars(self, idx: int) -> list[str]:
        return list(GROUPS.values())[idx]

    def select_group(self, idx: int):
        self._tab_bar.set_checked(idx)

    def set_kb_row_indicator(self, row: int | None):
        """Resalta la fila de 10 activa en el grupo visible; None la limpia."""
        active = self.current_group_index()
        for i, grid in enumerate(self._grids):
            grid.mark_row(row if i == active else None)

    def pick_slot(self, row: int, slot: int) -> bool:
        """Selecciona el carácter en la fila/posición (0-9) dadas del grupo
        activo. Devuelve False si esa posición no existe (fila corta)."""
        chars = self.group_chars(self.current_group_index())
        idx = row * 10 + slot
        if not (0 <= idx < len(chars)):
            return False
        self._grids[self.current_group_index()]._pick(chars[idx])
        return True
