#!/usr/bin/env python3
import sys
import os
import argparse

os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="durdrawgui",
        description="Editor de arte ASCII con animación",
    )
    p.add_argument(
        "--log-level",
        metavar="NIVEL",
        help="Tags de log activos: none | all | <tag,tag,...>  (default: app,io,theme)",
    )
    p.add_argument(
        "--log-dir",
        metavar="RUTA",
        help="Directorio para los archivos de log",
    )
    p.add_argument(
        "--config-dir",
        metavar="RUTA",
        help="Directorio de configuración del usuario",
    )
    p.add_argument(
        "file",
        nargs="?",
        metavar="ARCHIVO",
        help="Archivo .durg a abrir al iniciar",
    )
    return p.parse_args()


# Los overrides de entorno deben estar antes de importar core.log / core.config,
# ya que ambos resuelven sus rutas al importarse.
args = _parse_args()
if args.log_dir:
    os.environ["DURDRAW_LOG_DIR"] = args.log_dir
if args.log_level:
    os.environ["DURDRAW_LOG"] = args.log_level
if args.config_dir:
    os.environ["DURDRAW_CONFIG_DIR"] = args.config_dir

import core.log as log

log.info("=" * 60)
log.info(f"DurdrawGUI iniciando  (Python {sys.version.split()[0]})")
log.info("=" * 60)
log.info(f"Tags de log activos: {log.active_tags()}  (DURDRAW_LOG={os.environ.get('DURDRAW_LOG', '<no definido>')})")
log.info(f"Directorio de logs:  {log.log_dir()}")

from PySide6.QtWidgets import QApplication
from ui.app import App

if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    log.info(f"Platform: {qt_app.platformName()}")
    try:
        app = App(open_file=args.file)
        app.show()
        log.info("App visible — mainloop")
        sys.exit(qt_app.exec())
    except Exception:
        log.exception("Error fatal")
        raise
