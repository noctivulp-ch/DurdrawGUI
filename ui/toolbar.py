from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore    import Qt

from core.icons import get_icon

_TOOLS = [
    ("pencil",     "Lápiz (B)"),
    ("eraser",     "Borrador (E)"),
    ("fill",       "Relleno (G)"),
    ("eyedropper", "Cuentagotas (I)"),
    ("selection",  "Selección (S)"),
    ("line",       "Línea (L)"),
    ("rect",       "Rectángulo (R)"),
    ("ellipse",    "Elipse (O)"),
]


class ToolBar(QWidget):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app
        self.setFixedWidth(48)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._btns: dict[str, QPushButton] = {}
        for name, tip in _TOOLS:
            btn = QPushButton()
            btn.setIcon(get_icon(name))
            btn.setToolTip(tip)
            btn.setFixedSize(42, 36)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, n=name: app.select_tool(n))
            layout.addWidget(btn)
            self._btns[name] = btn
        layout.addStretch()

    def highlight(self, name: str):
        for n, btn in self._btns.items():
            btn.setChecked(n == name)
