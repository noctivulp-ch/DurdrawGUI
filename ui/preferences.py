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
from PySide6.QtGui  import QFont, QKeySequence, QFontDatabase, QColor

from core.shortcuts import ACTIONS, CATEGORY_ORDER, ShortcutManager
from core.config    import AppConfig
from core.theme     import NAMES as THEME_NAMES, SYSTEM, DARK, LIGHT


# ══════════════════════════════════════════════════════════════════════════════
class ShortcutCapture(QDialog):
    """Mini-diálogo que captura una pulsación de tecla."""

    def __init__(self, parent, current_key: str):
        super().__init__(parent)
        self.setWindowTitle("Captura de atajo")
        self.setModal(True)
        self.setFixedSize(340, 130)
        self._captured: str | None = None

        lbl = QLabel(f"Atajo actual: <b>{current_key or '(ninguno)'}</b><br>"
                     "Presiona la combinación de teclas deseada…<br>"
                     "(Supr/Retroceso para dejar el atajo sin asignar)")
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
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and \
                event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._captured = ""
            self._status.setText("Atajo eliminado")
            self.accept()
            return
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
    """Pestaña de edición de atajos de teclado — agrupada por categoría,
    hasta 2 combinaciones por acción."""

    _COL_LABEL = 0
    _COL_KEY1  = 1
    _COL_KEY2  = 2

    def __init__(self, shortcut_mgr: ShortcutManager):
        super().__init__()
        self._mgr = shortcut_mgr
        # (action_id, índice 0|1) → nueva tecla (sin aplicar todavía)
        self._dirty: dict[tuple[str, int], str] = {}

        by_category: dict[str, list[str]] = {}
        for action_id in ACTIONS:
            by_category.setdefault(shortcut_mgr.category(action_id), []).append(action_id)

        # self._ids[row] es el action_id de esa fila, o None si es una
        # cabecera de categoría (fila no editable, salteada en reset/click).
        self._ids: list[str | None] = []
        for category in CATEGORY_ORDER:
            if category not in by_category:
                continue
            self._ids.append(None)
            self._ids.extend(by_category[category])

        table = QTableWidget(len(self._ids), 3)
        table.setHorizontalHeaderLabels(["Acción", "Atajo 1", "Atajo 2"])
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)

        cat_iter = iter(c for c in CATEGORY_ORDER if c in by_category)
        for row, action_id in enumerate(self._ids):
            if action_id is None:
                header = QTableWidgetItem(next(cat_iter).upper())
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                header.setBackground(QColor("#3a3a3a"))
                header.setForeground(QColor("#e0e0e0"))
                table.setItem(row, self._COL_LABEL, header)
                table.setSpan(row, 0, 1, 3)
                continue
            label      = shortcut_mgr.label(action_id)
            key1, key2 = shortcut_mgr.keys(action_id)
            table.setItem(row, self._COL_LABEL, QTableWidgetItem(label))
            table.setItem(row, self._COL_KEY1,  QTableWidgetItem(key1))
            table.setItem(row, self._COL_KEY2,  QTableWidgetItem(key2))

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
        layout.addWidget(QLabel("Doble clic en Atajo 1 o Atajo 2 para reasignar. Ambos son opcionales."))
        layout.addLayout(btn_row)

    def _on_double_click(self, row: int, col: int):
        if self._ids[row] is None or col not in (self._COL_KEY1, self._COL_KEY2):
            return
        index     = 0 if col == self._COL_KEY1 else 1
        action_id = self._ids[row]
        current   = self._table.item(row, col).text()
        dlg = ShortcutCapture(self, current)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured is not None:
            new_key = dlg.captured
            self._dirty[(action_id, index)] = new_key
            self._table.item(row, col).setText(new_key)

    def _reset_selected(self):
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        for row in rows:
            self._reset_row(row)

    def _reset_all(self):
        for row in range(len(self._ids)):
            self._reset_row(row)

    def _reset_row(self, row: int):
        action_id = self._ids[row]
        if action_id is None:
            return
        _label, d1, d2, _cat = ACTIONS[action_id]
        self._dirty[(action_id, 0)] = d1
        self._dirty[(action_id, 1)] = d2
        self._table.item(row, self._COL_KEY1).setText(d1)
        self._table.item(row, self._COL_KEY2).setText(d2)

    def apply(self):
        """Aplica los cambios pendientes al ShortcutManager (sin guardar a disco)."""
        for (action_id, index), key in self._dirty.items():
            self._mgr.set_key(action_id, key, index)
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
