"""Diálogos Qt — modales nativos sin XWayland hacks."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QSpinBox, QRadioButton, QButtonGroup,
                               QDialogButtonBox, QLabel, QFrame, QMessageBox)
from PySide6.QtCore    import Qt

DEFAULT_W = 80
DEFAULT_H = 24

_W_MIN = 10
_H_MIN = 4
_MAX_CELLS = 150_000   # ancho × alto ≤ este límite


class NewCanvasDialog(QDialog):
    """QDialog completamente modal — el compositor lo gestiona directamente.

    Los QSpinBox usan un rango amplio (1-9999) para que el usuario pueda
    escribir cualquier número sin que Qt rechace dígitos intermedios.
    La validación real ocurre al aceptar.
    """

    def __init__(self, parent=None, current_w=DEFAULT_W,
                 current_h=DEFAULT_H, current_mode="16"):
        super().__init__(parent)
        self.setWindowTitle("Nuevo lienzo")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(340, 230)

        layout = QVBoxLayout(self)
        form   = QFormLayout()

        self._w = QSpinBox()
        self._w.setRange(1, 9999)
        self._w.setValue(current_w)
        self._w.setSuffix(f"  (mín. {_W_MIN})")

        self._h = QSpinBox()
        self._h.setRange(1, 9999)
        self._h.setValue(current_h)
        self._h.setSuffix(f"  (mín. {_H_MIN})")

        form.addRow("Ancho (columnas):", self._w)
        form.addRow("Alto (filas):",     self._h)
        layout.addLayout(form)

        vol_label = QLabel(f"Volumen máximo: {_MAX_CELLS:,} celdas  (ancho × alto)")
        vol_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(vol_label)

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

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setText("Crear lienzo")
        self._btns.accepted.connect(self._on_accept)
        self._btns.rejected.connect(self.reject)
        layout.addWidget(self._btns)

    def _on_accept(self):
        w, h = self._w.value(), self._h.value()
        if w < _W_MIN or h < _H_MIN:
            QMessageBox.warning(self, "Dimensiones inválidas",
                f"Ancho mínimo: {_W_MIN}  ·  Alto mínimo: {_H_MIN}.")
            return
        if w * h > _MAX_CELLS:
            QMessageBox.warning(self, "Lienzo demasiado grande",
                f"{w}×{h} = {w*h:,} celdas — supera el límite de {_MAX_CELLS:,}.\n"
                f"Ejemplos válidos: 500×300, 1000×150, 150×1000.")
            return
        self.accept()

    @property
    def result_data(self):
        return {
            "width":      self._w.value(),
            "height":     self._h.value(),
            "color_mode": "16" if self._r16.isChecked() else "256",
        }
