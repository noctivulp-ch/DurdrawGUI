from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QToolButton, QListWidget, QListWidgetItem,
                               QLabel, QSizePolicy)
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
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(1)
        btn_row.setContentsMargins(2, 0, 2, 2)
        for icon, tip, slot in (
            ("+", "Nueva capa",    app.add_layer),
            ("−", "Borrar capa",   app.delete_layer),
            ("↑", "Subir capa",    app.move_layer_up),
            ("↓", "Bajar capa",    app.move_layer_down),
        ):
            b = QToolButton()
            b.setText(icon)
            b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
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

    def _on_item_changed(self, item: QListWidgetItem):
        doc = self.app.doc
        real_idx = len(doc.layers) - 1 - self._list.row(item)
        if not (0 <= real_idx < len(doc.layers)):
            return
        visible = item.checkState() == Qt.CheckState.Checked
        layer = doc.layers[real_idx]
        if layer.visible != visible:
            layer.visible = visible
            self.app.canvas_widget.invalidate_all_frames()
            self.app.canvas_widget.render_frame()
