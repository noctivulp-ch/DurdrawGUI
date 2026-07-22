from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QFrame)
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QFont, QColor, QPalette

import core.log as log
import core.build_info as _bi

APP_NAME    = "DurdrawGUI"
APP_VERSION = "0.1.0"
APP_DESC    = "Editor de arte ASCII con animación, basado en durdraw."
APP_AUTHOR  = "NoctiVulp"
APP_LICENSE = "Licencia con fuente visible — ver archivo LICENSE"

_CHANNEL_LABELS = {
    "patreon": "Patrón (Patreon)",
    "regalo":  "Regalo",
    "dev":     "Desarrollo / no oficial",
}


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {APP_NAME}")
        self.setFixedSize(440, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(0)

        # ── Título ────────────────────────────────────────────────────────
        title = QLabel(APP_NAME)
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        version_lbl = QLabel(f"Versión {APP_VERSION}")
        fp = QFont()
        fp.setPointSize(10)
        version_lbl.setFont(fp)
        pal = version_lbl.palette()
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#888"))
        version_lbl.setPalette(pal)
        root.addWidget(version_lbl)

        root.addSpacing(12)

        # ── Separador ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        root.addSpacing(12)

        # ── Info básica ───────────────────────────────────────────────────
        for text in [APP_DESC, f"Autor: {APP_AUTHOR}", f"Licencia: {APP_LICENSE}"]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            root.addWidget(lbl)
            root.addSpacing(4)

        root.addSpacing(8)

        # ── Build ─────────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep2)
        root.addSpacing(8)

        canal_label = _CHANNEL_LABELS.get(_bi.BUILD_CHANNEL, _bi.BUILD_CHANNEL)
        if _bi.BUILD_OFFICIAL:
            build_status = f"Compilación oficial — {canal_label}"
            token_text   = _bi.BUILD_TOKEN
        else:
            build_status = "Compilación no oficial (desarrollo / fuente)"
            token_text   = "—"

        mono = QFont("monospace")
        mono.setPointSize(8)
        muted = QColor("#888")

        def _muted_row(key: str, value: str, selectable: bool = False) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(6)
            k = QLabel(key)
            k.setFixedWidth(56)
            v = QLabel(value)
            v.setFont(mono)
            if selectable:
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            p = v.palette()
            p.setColor(QPalette.ColorRole.WindowText, muted)
            v.setPalette(p)
            row.addWidget(k)
            row.addWidget(v, stretch=1)
            return row

        status_lbl = QLabel(build_status)
        status_lbl.setWordWrap(True)
        root.addWidget(status_lbl)
        root.addSpacing(6)

        if _bi.BUILD_OFFICIAL:
            root.addLayout(_muted_row("Token:", token_text, selectable=True))
            note = QLabel(
                "Verifica autenticidad comparando el token con el publicado en Patreon."
            )
            note.setWordWrap(True)
            note.setFont(mono)
            p3 = note.palette()
            p3.setColor(QPalette.ColorRole.WindowText, muted)
            note.setPalette(p3)
            root.addSpacing(4)
            root.addWidget(note)

        root.addSpacing(8)

        # ── Rutas de configuración ─────────────────────────────────────────
        cfg_dir  = Path.home() / ".config" / "durdrawgui"
        log_path = log.log_dir()
        for label, path in [("Config:", cfg_dir), ("Logs:", log_path)]:
            root.addLayout(_muted_row(label, str(path), selectable=True))

        root.addStretch()

        # ── Botón cerrar ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Cerrar")
        btn.setFixedWidth(90)
        btn.clicked.connect(self.accept)
        btn.setDefault(True)
        btn_row.addWidget(btn)
        root.addLayout(btn_row)
