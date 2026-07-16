import tkinter as tk
from tkinter import ttk
from core.tool_registry import get_ordered


class ToolBar(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", **kwargs)
        self.app = app
        self._buttons = {}

        for entry in get_ordered():
            if entry is None:
                ttk.Separator(self, orient="horizontal").pack(fill="x", pady=4, padx=2)
                continue
            cls = entry
            btn = tk.Button(
                self, text=cls.icon, width=3, font=("", 14),
                relief="flat", command=lambda n=cls.name: self.app.select_tool(n),
            )
            btn.pack(pady=2, padx=2)
            self._buttons[cls.name] = btn

    def highlight(self, tool_name):
        for name, btn in self._buttons.items():
            btn.config(relief="sunken" if name == tool_name else "flat")
