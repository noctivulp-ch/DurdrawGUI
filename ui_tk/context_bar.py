import tkinter as tk
from tkinter import ttk
from core.tool_registry import get_all
from core.brush import BUILTIN_NAMES

_PREVIEW_SIZE = 48   # px del canvas de preview del pincel


class ContextBar(tk.Frame):
    """Franja superior que muestra opciones de la herramienta activa.
    Los paneles se crean una sola vez por context_key; las herramientas que
    comparten clave (ej. line/rect/ellipse → 'shape') comparten el panel."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", height=54, **kwargs)
        self.pack_propagate(False)
        self.app = app
        self._panels = {}
        self._active_panel = None
        self._build_panels()

    def _build_panels(self):
        built = {}  # context_key → frame widget

        for cls in get_all().values():
            key = getattr(cls, "context_key", None)
            if key and key not in built:
                built[key] = self._make_panel(key)
            if key:
                self._panels[cls.name] = built[key]

        # Zoom — siempre visible en el lado derecho
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

    def _make_panel(self, key):
        """Crea el panel de contexto para un context_key dado."""
        if key == "brush":
            p = tk.Frame(self)

            # Preview canvas (izquierda)
            self._preview_canvas = tk.Canvas(
                p, width=_PREVIEW_SIZE, height=_PREVIEW_SIZE,
                bg="#111111", highlightthickness=1, highlightbackground="#444444"
            )
            self._preview_canvas.pack(side="left", padx=(6, 4), pady=3)

            # Selector de pincel
            center = tk.Frame(p)
            center.pack(side="left", fill="y")

            tk.Label(center, text="Pincel:").pack(anchor="w")
            self._brush_var = tk.StringVar(value="Punto 1×1")
            self._brush_combo = ttk.Combobox(
                center, textvariable=self._brush_var,
                values=self.app.brush_library.names,
                state="readonly", width=18
            )
            self._brush_combo.pack(anchor="w")
            self._brush_combo.bind("<<ComboboxSelected>>", self._on_brush_changed)

            # Botones import/export/eliminar
            btn_frame = tk.Frame(p)
            btn_frame.pack(side="left", padx=(6, 2), fill="y")
            tk.Button(btn_frame, text="Importar", width=8,
                      command=self._import_brush).pack(anchor="w", pady=1)
            btn_row = tk.Frame(btn_frame)
            btn_row.pack(anchor="w")
            tk.Button(btn_row, text="Exportar", width=7,
                      command=self._export_brush).pack(side="left", padx=(0, 2))
            self._del_btn = tk.Button(btn_row, text="Eliminar", width=7,
                                      command=self._delete_brush)
            self._del_btn.pack(side="left")

            self._redraw_brush_preview()
            return p

        if key == "fill":
            p = tk.Frame(self)
            tk.Label(p, text="Relleno exacto de char+color").pack(side="left", padx=6)
            return p

        if key == "selection":
            p = tk.Frame(self)
            tk.Label(p, text="Selección:").pack(side="left", padx=(6, 4))
            tk.Button(p, text="Copiar",   command=lambda: self.app.copy_selection()).pack(side="left", padx=2)
            tk.Button(p, text="Cortar",   command=lambda: self.app.cut_selection()).pack(side="left", padx=2)
            tk.Button(p, text="Pegar",    command=lambda: self.app.paste_clipboard()).pack(side="left", padx=2)
            tk.Button(p, text="Borrar",   command=lambda: self.app.clear_selection()).pack(side="left", padx=2)
            tk.Button(p, text="Deselec.", command=lambda: self.app.deselect()).pack(side="left", padx=2)
            return p

        if key == "eyedropper":
            p = tk.Frame(self)
            tk.Label(p, text="Cuentagotas — clic para tomar char+color").pack(side="left", padx=6)
            return p

        if key == "shape":
            p = tk.Frame(self)
            tk.Label(p, text="Modo:").pack(side="left", padx=(6, 2))
            self._shape_filled = tk.BooleanVar(value=False)
            tk.Radiobutton(p, text="Borde",   value=False,
                           variable=self._shape_filled).pack(side="left")
            tk.Radiobutton(p, text="Relleno", value=True,
                           variable=self._shape_filled).pack(side="left")
            return p

        # Panel vacío para context_keys no reconocidos
        return tk.Frame(self)

    # ── API pública ────────────────────────────────────────────────────────

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
    def active_brush_name(self) -> str:
        v = getattr(self, "_brush_var", None)
        return v.get() if v else "Punto 1×1"

    @property
    def shape_filled(self):
        return self._shape_filled.get()

    # ── Pincel: preview, callbacks, import/export ──────────────────────────

    def _on_brush_changed(self, *_):
        self._redraw_brush_preview()
        # Actualiza el cursor del canvas si el puntero está sobre él
        cw = getattr(self.app, "canvas_widget", None)
        if cw and cw._cursor_cell:
            col, row = cw._cursor_cell
            brush = self.app.active_brush
            cw._renderer.draw_brush_cursor(
                col, row, brush.cells,
                self.app.fg_char, self.app.fg_color, self.app.bg_color,
                self.app.color_service,
            )

    def _redraw_brush_preview(self):
        """Dibuja la forma del pincel activo en el canvas de preview."""
        c = self._preview_canvas
        W = _PREVIEW_SIZE
        c.delete("all")
        c.create_rectangle(0, 0, W, W, fill="#111111", outline="")

        brush = self.app.brush_library.get(self._brush_var.get())
        if not brush or not brush.cells:
            return

        r0, cc0, r1, cc1 = brush.bbox
        rows = r1 - r0 + 1
        cols = cc1 - cc0 + 1
        # Escala: deja 1 celda de margen alrededor
        cell_sz = max(2.0, W / (max(rows, cols) + 2))
        ox = (W - cols * cell_sz) / 2
        oy = (W - rows * cell_sz) / 2

        cell_set = set(brush.cells)
        for dr in range(r0, r1 + 1):
            for dc in range(cc0, cc1 + 1):
                x = ox + (dc - cc0) * cell_sz
                y = oy + (dr - r0) * cell_sz
                color = "#4488ff" if (dr, dc) in cell_set else "#1e1e1e"
                c.create_rectangle(
                    x + 1, y + 1, x + cell_sz - 1, y + cell_sz - 1,
                    fill=color, outline=""
                )

        # Estado del botón eliminar
        if hasattr(self, "_del_btn"):
            is_builtin = self._brush_var.get() in BUILTIN_NAMES
            self._del_btn.config(state="disabled" if is_builtin else "normal")

    def _refresh_combobox(self):
        self._brush_combo["values"] = self.app.brush_library.names

    def _import_brush(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Importar pincel",
            filetypes=[("JSON de pincel", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            brush = self.app.brush_library.import_from(path)
            self._refresh_combobox()
            self._brush_var.set(brush.name)
            self._redraw_brush_preview()
            messagebox.showinfo("Importar", f"Pincel '{brush.name}' importado.")
        except Exception as e:
            messagebox.showerror("Error al importar", str(e))

    def _export_brush(self):
        from tkinter import filedialog, messagebox
        name = self._brush_var.get()
        if not name:
            return
        path = filedialog.asksaveasfilename(
            title="Exportar pincel",
            defaultextension=".json",
            filetypes=[("JSON de pincel", "*.json")],
            initialfile=f"{name}.json",
        )
        if not path:
            return
        if self.app.brush_library.export_to(name, path):
            messagebox.showinfo("Exportar", f"Pincel '{name}' exportado.")
        else:
            messagebox.showerror("Error", "No se pudo exportar el pincel.")

    def _delete_brush(self):
        from tkinter import messagebox
        name = self._brush_var.get()
        if name in BUILTIN_NAMES:
            return
        if messagebox.askyesno("Eliminar pincel", f"¿Eliminar '{name}'?"):
            self.app.brush_library.delete(name)
            self._refresh_combobox()
            self._brush_var.set(self.app.brush_library.names[0])
            self._redraw_brush_preview()
