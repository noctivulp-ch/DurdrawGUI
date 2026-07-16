from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QSpinBox,
                               QComboBox, QPushButton, QStackedWidget,
                               QFileDialog, QMessageBox)
from PySide6.QtCore    import Qt

from core.brush import BUILTIN_NAMES


class _ZoomWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        self._lbl = QLabel("100%")
        self._lbl.setMinimumWidth(50)
        layout.addWidget(QLabel("Zoom:"))
        layout.addWidget(self._lbl)
        layout.addStretch()

    def set_zoom(self, pct: int):
        self._lbl.setText(f"{pct}%")


class _PencilPanel(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)

        layout.addWidget(QLabel("Pincel:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(140)
        self._combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self._combo)

        for lbl, slot in (("Importar", self._import),
                          ("Exportar", self._export),
                          ("Borrar",   self._delete)):
            b = QPushButton(lbl)
            b.setFixedHeight(24)
            b.clicked.connect(slot)
            layout.addWidget(b)

        layout.addStretch()
        self._refresh_combo()

    @property
    def active_brush_name(self) -> str:
        return self._combo.currentText()

    def _refresh_combo(self):
        lib = self.app.brush_library
        self._combo.blockSignals(True)
        self._combo.clear()
        for name in lib.names:
            self._combo.addItem(name)
        self._combo.blockSignals(False)

    def _on_changed(self, name: str):
        pass   # el nombre se lee en active_brush_name cuando la herramienta lo necesita

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar pincel", "", "JSON (*.json)"
        )
        if path:
            try:
                self.app.brush_library.import_from(path)
                self._refresh_combo()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _export(self):
        name = self._combo.currentText()
        if not name:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar pincel", f"{name}.json", "JSON (*.json)"
        )
        if path:
            try:
                self.app.brush_library.export_to(name, path)
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete(self):
        name = self._combo.currentText()
        if not name or name in BUILTIN_NAMES:
            QMessageBox.warning(self, "No borrable",
                                "Los pinceles built-in no se pueden borrar.")
            return
        self.app.brush_library.delete(name)
        self._refresh_combo()


class ContextBar(QWidget):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack  = QStackedWidget()
        self._zoom_w = _ZoomWidget()
        self._pencil = _PencilPanel(self, app)

        # páginas: 0=genérica(zoom), 1=pencil/eraser
        self._stack.addWidget(self._zoom_w)
        self._stack.addWidget(self._pencil)
        layout.addWidget(self._stack)

    def set_zoom(self, pct: int):
        self._zoom_w.set_zoom(pct)

    def switch(self, tool_name: str):
        if tool_name in ("pencil", "eraser"):
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    @property
    def active_brush_name(self) -> str:
        return self._pencil.active_brush_name
