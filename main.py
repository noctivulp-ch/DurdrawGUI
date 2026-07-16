#!/usr/bin/env python3
import tkinter as tk
import tkinter.font  # noqa: F401 — necesario para tk.font en canvas.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core.log as log

if __name__ == "__main__":
    log.info("=" * 60)
    log.info(f"DurdrawGUI iniciando  (Python {sys.version.split()[0]})")
    log.info(f"Log: {log.LOG_PATH}")
    log.info("=" * 60)

    from ui.app import App
    root = tk.Tk()
    log.info(f"Tk {tk.TkVersion}  windowing={root.tk.call('tk', 'windowingsystem')}")
    try:
        app = App(root)
        log.info("App inicializada — entrando en mainloop")
        root.mainloop()
        log.info("mainloop terminó normalmente")
    except Exception:
        log.exception("Error fatal en mainloop")
        raise
