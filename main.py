#!/usr/bin/env python3
import tkinter as tk
import tkinter.font  # noqa: F401 — necesario para tk.font en canvas.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import App

if __name__ == "__main__":
    root = tk.Tk()
    app  = App(root)
    root.mainloop()
