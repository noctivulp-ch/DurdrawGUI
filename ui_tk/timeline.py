import tkinter as tk
from tkinter import ttk


class Timeline(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", **kwargs)
        self.app = app
        self._play_job = None

        # Controles de reproducción
        ctrl = tk.Frame(self)
        ctrl.pack(side="left", padx=4)

        tk.Button(ctrl, text="|◀", width=2, command=self.app.goto_first_frame).grid(row=0, column=0)
        tk.Button(ctrl, text="◀",  width=2, command=self.app.prev_frame).grid(row=0, column=1)
        self._play_btn = tk.Button(ctrl, text="▶", width=2, command=self._toggle_play)
        self._play_btn.grid(row=0, column=2)
        tk.Button(ctrl, text="▶|", width=2, command=self.app.goto_last_frame).grid(row=0, column=3)

        # Frame actual / total
        self._frame_var = tk.StringVar(value="1 / 1")
        tk.Label(ctrl, textvariable=self._frame_var, width=8).grid(row=0, column=4, padx=6)

        # FPS
        tk.Label(ctrl, text="FPS:").grid(row=0, column=5)
        self._fps_var = tk.IntVar(value=10)
        ttk.Spinbox(ctrl, from_=1, to=60, textvariable=self._fps_var,
                    width=4).grid(row=0, column=6)

        # Botones de gestión de frames
        tk.Button(ctrl, text="+F", width=3,
                  command=self.app.add_frame).grid(row=0, column=7, padx=(12, 2))
        tk.Button(ctrl, text="+F◁", width=4,
                  command=self.app.duplicate_frame).grid(row=0, column=8, padx=2)
        tk.Button(ctrl, text="-F", width=3,
                  command=self.app.delete_frame).grid(row=0, column=9, padx=2)

    # ── Reproducción ──────────────────────────────────────────────────────────

    def _toggle_play(self):
        if self._play_job:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        self._play_btn.config(text="⏹")
        self._advance()

    def _advance(self):
        self.app.next_frame(wrap=True)
        delay = max(16, 1000 // self._fps_var.get())
        self._play_job = self.app.root.after(delay, self._advance)

    def _stop_play(self):
        if self._play_job:
            self.app.root.after_cancel(self._play_job)
            self._play_job = None
        self._play_btn.config(text="▶")

    def stop_play(self):
        self._stop_play()

    def update_display(self, current, total):
        self._frame_var.set(f"{current} / {total}")
