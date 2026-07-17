"""Diálogo de preferencias — Atajos de teclado e Interfaz."""

from __future__ import annotations
from typing import Callable

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QGroupBox, QRadioButton, QHeaderView,
    QAbstractItemView, QSizePolicy, QFontComboBox,
)
from PySide6.QtCore import Qt, QKeyCombination
from PySide6.QtGui  import QFont, QKeySequence, QFontDatabase

from core.shortcuts import ACTIONS, ShortcutManager
from core.config    import AppConfig
from core.theme     import NAMES as THEME_NAMES, SYSTEM, DARK, LIGHT


# ══════════════════════════════════════════════════════════════════════════════
class ShortcutCapture(QDialog):
    """Mini-diálogo que captura una pulsación de tecla."""

    def __init__(self, parent, current_key: str):
        super().__init__(parent)
        self.setWindowTitle("Captura de atajo")
        self.setModal(True)
        self.setFixedSize(320, 120)
        self._captured: str | None = None

        lbl = QLabel(f"Atajo actual: <b>{current_key or '(ninguno)'}</b><br>"
                     "Presiona la combinación de teclas deseada…")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(lbl)
        layout.addWidget(self._status)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
                   Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return  # esperar tecla real
        mods = event.modifiers()
        seq  = QKeySequence(QKeyCombination(mods, Qt.Key(key)))
        self._captured = seq.toString(QKeySequence.SequenceFormat.PortableText)
        self._status.setText(f"Capturado: <b>{self._captured}</b>")
        self.accept()

    @property
    def captured(self) -> str | None:
        return self._captured


# ══════════════════════════════════════════════════════════════════════════════
class _ShortcutsTab(QWidget):
    """Pestaña de edición de atajos de teclado."""

    _COL_LABEL = 0
    _COL_KEY   = 1

    def __init__(self, shortcut_mgr: ShortcutManager):
        super().__init__()
        self._mgr   = shortcut_mgr
        self._dirty: dict[str, str] = {}   # action_id → nueva tecla (sin aplicar)

        table = QTableWidget(len(ACTIONS), 2)
        table.setHorizontalHeaderLabels(["Acción", "Atajo"])
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)

        self._ids: list[str] = list(ACTIONS.keys())
        for row, action_id in enumerate(self._ids):
            label = shortcut_mgr.label(action_id)
            key   = shortcut_mgr.key(action_id)
            table.setItem(row, self._COL_LABEL, QTableWidgetItem(label))
            table.setItem(row, self._COL_KEY,   QTableWidgetItem(key))

        table.cellDoubleClicked.connect(self._on_double_click)
        self._table = table

        btn_reset_sel = QPushButton("Restablecer seleccionado")
        btn_reset_sel.clicked.connect(self._reset_selected)
        btn_reset_all = QPushButton("Restablecer todos")
        btn_reset_all.clicked.connect(self._reset_all)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_reset_sel)
        btn_row.addWidget(btn_reset_all)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(table)
        layout.addLayout(btn_row)

    def _on_double_click(self, row: int, _col: int):
        action_id = self._ids[row]
        current   = self._table.item(row, self._COL_KEY).text()
        dlg = ShortcutCapture(self, current)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured:
            new_key = dlg.captured
            self._dirty[action_id] = new_key
            self._table.item(row, self._COL_KEY).setText(new_key)

    def _reset_selected(self):
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        for row in rows:
            action_id = self._ids[row]
            default   = ACTIONS[action_id][1]
            self._dirty[action_id] = default
            self._table.item(row, self._COL_KEY).setText(default)

    def _reset_all(self):
        for row, action_id in enumerate(self._ids):
            default = ACTIONS[action_id][1]
            self._dirty[action_id] = default
            self._table.item(row, self._COL_KEY).setText(default)

    def apply(self):
        """Aplica los cambios pendientes al ShortcutManager (sin guardar a disco)."""
        for action_id, key in self._dirty.items():
            self._mgr.set_key(action_id, key)
        self._dirty.clear()


# ══════════════════════════════════════════════════════════════════════════════
class _InterfaceTab(QWidget):
    """Pestaña de opciones de interfaz (minimapa)."""

    _CORNERS = [
        ("TR", "Superior derecha"),
        ("TL", "Superior izquierda"),
        ("BR", "Inferior derecha"),
        ("BL", "Inferior izquierda"),
    ]

    _THEMES = [
        (DARK,   THEME_NAMES[DARK]),
        (LIGHT,  THEME_NAMES[LIGHT]),
        (SYSTEM, THEME_NAMES[SYSTEM]),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config = config

        # ── Tema ──────────────────────────────────────────────────────────
        theme_group  = QGroupBox("Tema de la interfaz")
        theme_layout = QVBoxLayout(theme_group)
        current_theme = config.get("theme", DARK)
        self._theme_radios: dict[str, QRadioButton] = {}

        for code, label in self._THEMES:
            rb = QRadioButton(label)
            if code == current_theme:
                rb.setChecked(True)
            self._theme_radios[code] = rb
            theme_layout.addWidget(rb)

        # ── Fuente del canvas ─────────────────────────────────────────────
        font_group  = QGroupBox("Fuente del canvas")
        font_layout = QVBoxLayout(font_group)

        self._font_combo = QFontComboBox()
        self._font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self._font_combo.setCurrentFont(QFont(config.get("canvas_font", "DejaVu Sans Mono")))

        font_layout.addWidget(self._font_combo)

        # ── Esquina del minimapa ──────────────────────────────────────────
        minimap_group  = QGroupBox("Esquina del minimapa")
        minimap_layout = QVBoxLayout(minimap_group)
        current_corner = config.get("minimap_corner", "TR")
        self._corner_radios: dict[str, QRadioButton] = {}

        for code, label in self._CORNERS:
            rb = QRadioButton(label)
            if code == current_corner:
                rb.setChecked(True)
            self._corner_radios[code] = rb
            minimap_layout.addWidget(rb)

        layout = QVBoxLayout(self)
        layout.addWidget(theme_group)
        layout.addWidget(font_group)
        layout.addWidget(minimap_group)
        layout.addStretch()

    def apply(self):
        """Aplica la selección al AppConfig (sin guardar a disco)."""
        for code, rb in self._theme_radios.items():
            if rb.isChecked():
                self._config.set("theme", code)
                break
        self._config.set("canvas_font", self._font_combo.currentFont().family())
        for code, rb in self._corner_radios.items():
            if rb.isChecked():
                self._config.set("minimap_corner", code)
                break


# ══════════════════════════════════════════════════════════════════════════════
class PreferencesDialog(QDialog):
    """Diálogo de preferencias con pestañas Atajos e Interfaz."""

    def __init__(
        self,
        parent,
        shortcut_mgr: ShortcutManager,
        config: AppConfig,
        on_accept: Callable | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self.setMinimumSize(520, 480)
        self._on_accept = on_accept

        tabs = QTabWidget()

        self._sc_tab  = _ShortcutsTab(shortcut_mgr)
        self._ifc_tab = _InterfaceTab(config)
        tabs.addTab(self._sc_tab,  "Atajos de teclado")
        tabs.addTab(self._ifc_tab, "Interfaz")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _on_ok(self):
        self._sc_tab.apply()
        self._ifc_tab.apply()
        if self._on_accept:
            self._on_accept()
        self.accept()
