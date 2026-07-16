import tkinter as tk
from tkinter import ttk


class StatusBar(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, relief="sunken", bd=1, **kwargs)

        self._pos_var   = tk.StringVar(value="")
        self._char_var  = tk.StringVar(value="")
        self._frame_var = tk.StringVar(value="F:1/1")
        self._tool_var  = tk.StringVar(value="pencil")

        tk.Label(self, textvariable=self._pos_var,   anchor="w",
                 width=12).pack(side="left", padx=4)
        ttk.Separator(self, orient="vertical").pack(side="left", fill="y", padx=2)
        tk.Label(self, textvariable=self._char_var,  anchor="w",
                 width=10).pack(side="left", padx=4)
        ttk.Separator(self, orient="vertical").pack(side="left", fill="y", padx=2)
        tk.Label(self, textvariable=self._frame_var, anchor="w",
                 width=10).pack(side="left", padx=4)
        ttk.Separator(self, orient="vertical").pack(side="left", fill="y", padx=2)
        tk.Label(self, textvariable=self._tool_var,  anchor="w").pack(side="left", padx=4)

    def set_pos(self, col, row, ch=None, fg=None, bg=None):
        if col is None:
            self._pos_var.set("")
            self._char_var.set("")
        else:
            self._pos_var.set(f"C:{col} L:{row}")
            ch_display = repr(ch) if ch and ch != " " else "' '"
            self._char_var.set(f"{ch_display} {fg}/{bg}")

    def set_frame(self, current, total):
        self._frame_var.set(f"F:{current}/{total}")

    def set_tool(self, name):
        self._tool_var.set(name)
