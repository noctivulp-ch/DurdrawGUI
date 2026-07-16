import tkinter as tk


class LayerPanel(tk.Frame):
    """Panel lateral con lista de capas, toggles de visibilidad y botones de gestión."""

    _BG_IDLE    = "#1a1a1a"
    _BG_ACTIVE  = "#2a5a2a"
    _BG_HEADER  = "#252525"
    _BG_BTN     = "#333333"
    _FG_WHITE   = "#e8e8e8"
    _FG_DIM     = "#888888"
    _FG_VIS     = "#88ee88"
    _FG_HIDDEN  = "#444444"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=self._BG_HEADER, **kwargs)
        self.app = app

        # ── Cabecera ──────────────────────────────────────────────────────
        header = tk.Frame(self, bg=self._BG_HEADER)
        header.pack(fill="x")
        tk.Label(
            header, text="Capas",
            fg=self._FG_WHITE, bg=self._BG_HEADER,
            font=("Monospace", 9, "bold"),
        ).pack(side="left", padx=6, pady=3)

        # ── Lista de capas ────────────────────────────────────────────────
        self._list_frame = tk.Frame(self, bg=self._BG_IDLE)
        self._list_frame.pack(fill="both", expand=True)

        # ── Barra de botones ──────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=self._BG_HEADER)
        btn_row.pack(fill="x", pady=1)
        for label, cmd, tooltip in [
            ("+",  app.add_layer,       "Nueva capa"),
            ("−",  app.delete_layer,    "Eliminar capa"),
            ("↑",  app.move_layer_up,   "Subir capa"),
            ("↓",  app.move_layer_down, "Bajar capa"),
        ]:
            tk.Button(
                btn_row, text=label, width=3, command=cmd,
                fg=self._FG_WHITE, bg=self._BG_BTN,
                activebackground="#555555", relief="flat",
                cursor="hand2",
            ).pack(side="left", padx=1, pady=1)

        # Suscripción al bus
        app.bus.on("layers_changed", lambda _: self.refresh())
        self.refresh()

    # ── Refresco de la lista ───────────────────────────────────────────────

    def refresh(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        doc = self.app.doc
        # Capas en orden visual: la más alta (índice mayor) aparece arriba
        for display_idx, layer in enumerate(reversed(doc.layers)):
            real_idx = len(doc.layers) - 1 - display_idx
            is_active = (real_idx == doc.active_layer_idx)
            self._build_row(layer, real_idx, is_active)

    def _build_row(self, layer, real_idx, is_active):
        bg = self._BG_ACTIVE if is_active else self._BG_IDLE
        row = tk.Frame(self._list_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=1, pady=1)

        # Icono de visibilidad
        eye_lbl = tk.Label(
            row,
            text="●" if layer.visible else "○",
            fg=self._FG_VIS if layer.visible else self._FG_HIDDEN,
            bg=bg, width=2,
            font=("Monospace", 9),
            cursor="hand2",
        )
        eye_lbl.pack(side="left", padx=(2, 0))

        # Nombre de la capa
        name_lbl = tk.Label(
            row,
            text=layer.name,
            fg=self._FG_WHITE if is_active else self._FG_DIM,
            bg=bg,
            font=("Monospace", 9),
            anchor="w",
        )
        name_lbl.pack(side="left", fill="x", expand=True, padx=4)

        # El ojo toggle detiene la propagación para no activar la capa también
        def _toggle(e, i=real_idx):
            self._toggle_visible(i)
            return "break"

        def _select(e, i=real_idx):
            self._select_layer(i)

        def _rename(e, i=real_idx):
            self._rename_layer(i)

        eye_lbl.bind("<ButtonPress-1>", _toggle)
        row.bind("<ButtonPress-1>",     _select)
        name_lbl.bind("<ButtonPress-1>",  _select)
        name_lbl.bind("<Double-Button-1>", _rename)

    # ── Acciones ───────────────────────────────────────────────────────────

    def _select_layer(self, idx):
        self.app.doc.set_active_layer(idx)
        self.app.bus.emit("layers_changed", None)
        self.app.canvas_widget.render_frame()

    def _toggle_visible(self, idx):
        layer = self.app.doc.layers[idx]
        layer.visible = not layer.visible
        self.refresh()
        self.app.canvas_widget.render_frame()

    def _rename_layer(self, idx):
        layer = self.app.doc.layers[idx]
        dlg = tk.Toplevel(self)
        dlg.title("Renombrar capa")
        dlg.resizable(False, False)

        tk.Label(dlg, text="Nombre:").pack(padx=12, pady=(10, 2))
        entry = tk.Entry(dlg, width=24)
        entry.insert(0, layer.name)
        entry.select_range(0, tk.END)
        entry.pack(padx=12, pady=4)
        entry.focus_set()

        def _ok():
            name = entry.get().strip()
            if name:
                layer.name = name
            dlg.destroy()
            self.refresh()

        tk.Button(dlg, text="Aceptar", command=_ok).pack(pady=(4, 10))
        dlg.bind("<Return>", lambda e: _ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.transient(self)
        dlg.grab_set()
        self.wait_window(dlg)
