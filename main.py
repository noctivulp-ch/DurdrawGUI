#!/usr/bin/env python3
import sys
import os
os.environ.setdefault("QT_QPA_PLATFORM", "wayland")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core.log as log

log.info("=" * 60)
log.info(f"DurdrawGUI iniciando  (Python {sys.version.split()[0]})")
log.info("=" * 60)

from PySide6.QtWidgets import QApplication
from ui.app import App

if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    log.info(f"Platform: {qt_app.platformName()}")
    try:
        app = App()
        app.show()
        log.info("App visible — mainloop")
        sys.exit(qt_app.exec())
    except Exception:
        log.exception("Error fatal")
        raise
