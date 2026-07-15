import tkinter as tk
from tkinter import ttk


class ContextBar(tk.Frame):
    """Franja superior que muestra opciones de la herramienta activa."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", height=32, **kwargs)
        self.pack_propagate(False)
        self.app = app
        self._panels = {}
        self._active_panel = None
        self._build_panels()

    def _build_panels(self):
        # ── Panel: lápiz / borrador ────────────────────────────────────────
        p = tk.Frame(self)
        tk.Label(p, text="Tam:").pack(side="left", padx=(6, 2))
        self._brush_size = tk.IntVar(value=1)
        for s in (1, 2, 3):
            tk.Radiobutton(p, text=str(s), value=s,
                           variable=self._brush_size).pack(side="left")
        self._panels["pencil"]  = p
        self._panels["eraser"]  = p

        # ── Panel: relleno ────────────────────────────────────────────────
        p2 = tk.Frame(self)
        tk.Label(p2, text="Relleno exacto de char+color").pack(side="left", padx=6)
        self._panels["fill"] = p2

        # ── Panel: selección ─────────────────────────────────────────────
        p3 = tk.Frame(self)
        tk.Label(p3, text="Selección:").pack(side="left", padx=(6, 4))
        tk.Button(p3, text="Copiar",   command=lambda: self.app.copy_selection()).pack(side="left", padx=2)
        tk.Button(p3, text="Cortar",   command=lambda: self.app.cut_selection()).pack(side="left", padx=2)
        tk.Button(p3, text="Pegar",    command=lambda: self.app.paste_clipboard()).pack(side="left", padx=2)
        tk.Button(p3, text="Borrar",   command=lambda: self.app.clear_selection()).pack(side="left", padx=2)
        tk.Button(p3, text="Deselec.", command=lambda: self.app.deselect()).pack(side="left", padx=2)
        self._panels["selection"] = p3

        # ── Panel: eyedropper / default ───────────────────────────────────
        p4 = tk.Frame(self)
        tk.Label(p4, text="Cuentagotas — clic para tomar char+color").pack(side="left", padx=6)
        self._panels["eyedropper"] = p4

        # ── Panel: herramientas de forma (línea / rectángulo / elipse) ────
        p5 = tk.Frame(self)
        tk.Label(p5, text="Modo:").pack(side="left", padx=(6, 2))
        self._shape_filled = tk.BooleanVar(value=False)
        tk.Radiobutton(p5, text="Borde",   value=False, variable=self._shape_filled).pack(side="left")
        tk.Radiobutton(p5, text="Relleno", value=True,  variable=self._shape_filled).pack(side="left")
        self._panels["line"]    = p5
        self._panels["rect"]    = p5
        self._panels["ellipse"] = p5

        # ── Info de zoom (siempre visible, lado derecho) ──────────────────
        right = tk.Frame(self)
        right.pack(side="right", padx=8)
        tk.Label(right, text="Zoom:").pack(side="left")
        self._zoom_var = tk.StringVar(value="100%")
        tk.Label(right, textvariable=self._zoom_var, width=6).pack(side="left")
        tk.Button(right, text="−", width=2,
                  command=lambda: self.app.zoom_out()).pack(side="left", padx=1)
        tk.Button(right, text="+", width=2,
                  command=lambda: self.app.zoom_in()).pack(side="left", padx=1)
        tk.Button(right, text="1:1", width=3,
                  command=lambda: self.app.zoom_reset()).pack(side="left", padx=1)

    def switch(self, tool_name):
        if self._active_panel:
            self._active_panel.pack_forget()
        panel = self._panels.get(tool_name)
        if panel:
            panel.pack(side="left", fill="y")
            self._active_panel = panel

    def set_zoom(self, pct):
        self._zoom_var.set(f"{pct}%")

    @property
    def brush_size(self):
        return self._brush_size.get()

    @property
    def shape_filled(self):
        return self._shape_filled.get()
