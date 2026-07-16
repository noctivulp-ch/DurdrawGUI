"""Diálogos Qt — modales nativos sin XWayland hacks."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QSpinBox, QRadioButton, QButtonGroup,
                               QPushButton, QDialogButtonBox, QLabel,
                               QFrame)
from PySide6.QtCore    import Qt

DEFAULT_W = 80
DEFAULT_H = 24


class NewCanvasDialog(QDialog):
    """QDialog completamente modal — el compositor lo gestiona directamente."""

    def __init__(self, parent=None, current_w=DEFAULT_W,
                 current_h=DEFAULT_H, current_mode="16"):
        super().__init__(parent)
        self.setWindowTitle("Nuevo lienzo")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(320, 200)

        layout = QVBoxLayout(self)
        form   = QFormLayout()

        self._w = QSpinBox(); self._w.setRange(10, 500); self._w.setValue(current_w)
        self._h = QSpinBox(); self._h.setRange(4,  300); self._h.setValue(current_h)
        form.addRow("Ancho (columnas):", self._w)
        form.addRow("Alto (filas):",     self._h)
        layout.addLayout(form)

        layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Colores:"))
        self._grp  = QButtonGroup(self)
        self._r16  = QRadioButton("16 ANSI")
        self._r256 = QRadioButton("256 xterm")
        self._grp.addButton(self._r16,  0)
        self._grp.addButton(self._r256, 1)
        (self._r16 if current_mode == "16" else self._r256).setChecked(True)
        color_row.addWidget(self._r16)
        color_row.addWidget(self._r256)
        color_row.addStretch()
        layout.addLayout(color_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Crear lienzo")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def result_data(self):
        return {
            "width":      self._w.value(),
            "height":     self._h.value(),
            "color_mode": "16" if self._r16.isChecked() else "256",
        }
