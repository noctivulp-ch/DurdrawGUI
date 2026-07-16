from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QListWidget, QListWidgetItem,
                               QLabel, QCheckBox)
from PySide6.QtCore    import Qt


class LayerPanel(QWidget):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app
        self.setMinimumWidth(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        layout.addWidget(QLabel("Capas"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for icon, tip, slot in (
            ("+", "Nueva capa",    app.add_layer),
            ("−", "Borrar capa",   app.delete_layer),
            ("↑", "Subir capa",    app.move_layer_up),
            ("↓", "Bajar capa",    app.move_layer_down),
        ):
            b = QPushButton(icon); b.setFixedSize(28, 24)
            b.setToolTip(tip); b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        app.bus.on("layers_changed", lambda _: self.refresh())
        self.refresh()

    def refresh(self):
        self._list.blockSignals(True)
        self._list.clear()
        doc = self.app.doc
        for i, layer in enumerate(reversed(doc.layers)):
            item = QListWidgetItem(layer.name or f"Capa {i+1}")
            item.setCheckState(Qt.CheckState.Checked if layer.visible
                               else Qt.CheckState.Unchecked)
            self._list.addItem(item)
        active_display = len(doc.layers) - 1 - doc.active_layer_idx
        self._list.setCurrentRow(active_display)
        self._list.blockSignals(False)

    def _on_row_changed(self, row: int):
        if row < 0:
            return
        doc = self.app.doc
        real_idx = len(doc.layers) - 1 - row
        if real_idx != doc.active_layer_idx:
            doc.set_active_layer(real_idx)
            self.app.canvas_widget.render_frame()
