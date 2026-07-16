import tkinter as tk
from tkinter import ttk

# ── Conjuntos de caracteres ────────────────────────────────────────────────────

_CHARS_STD = (
    [chr(c) for c in range(32, 127)]
    + list("░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀"
           "αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■")
)


def _load_unicode_chars(*block_names):
    """Carga bloques unicode de durdraw_charsets y devuelve lista de chars."""
    try:
        from core.durdraw.durdraw_charsets import load_unicode_block
    except ImportError:
        return []
    chars = []
    for name in block_names:
        blocks = load_unicode_block(name) or []
        for row in blocks:
            for cp in row.values():
                if isinstance(cp, int) and cp > 0:
                    try:
                        chars.append(chr(cp))
                    except (ValueError, OverflowError):
                        pass
    return chars


class ColorPanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", **kwargs)
        self.app = app

        # Carga de charsets Unicode al crear el panel (no al importar el módulo)
        chars_bloques = _load_unicode_chars("Block Elements", "Box Drawing", "Geometric Shapes")
        chars_braille = _load_unicode_chars("Braille Patterns")
        chars_flechas = _load_unicode_chars("Arrows", "Miscellaneous Symbols and Arrows")

        # ── Indicadores frente/fondo ───────────────────────────────────────
        top = tk.LabelFrame(self, text="Color activo")
        top.pack(fill="x", padx=4, pady=4)

        self._fg_swatch = tk.Canvas(top, width=28, height=28, bd=1, relief="sunken")
        self._bg_swatch = tk.Canvas(top, width=28, height=28, bd=1, relief="sunken")
        self._fg_swatch.grid(row=0, column=0, padx=4, pady=4)
        self._bg_swatch.grid(row=0, column=1, padx=4, pady=4)
        tk.Label(top, text="FG").grid(row=1, column=0)
        tk.Label(top, text="BG").grid(row=1, column=1)

        swap_btn = tk.Button(top, text="⇄", command=self.app.swap_colors)
        swap_btn.grid(row=0, column=2, padx=4)

        self._char_label = tk.Label(top, text="' '", font=("Monospace", 18),
                                    bd=1, relief="sunken", width=3)
        self._char_label.grid(row=0, column=3, padx=4)
        tk.Label(top, text="Char").grid(row=1, column=3)

        # ── Paleta de colores ──────────────────────────────────────────────
        self._pal_frame = tk.LabelFrame(self, text="Paleta")
        self._pal_frame.pack(fill="x", padx=4, pady=4)
        self._pal_cells = []
        self._build_palette_grid()

        # ── Selector de carácter (notebook) ───────────────────────────────
        char_outer = tk.LabelFrame(self, text="Carácter")
        char_outer.pack(fill="both", expand=True, padx=4, pady=4)

        nb = ttk.Notebook(char_outer)
        nb.pack(fill="both", expand=True)

        self._char_canvases = {}
        tabs = [
            ("Std",    _CHARS_STD,    "#EEE"),
            ("Blq",    chars_bloques, "#CCFFCC"),
            ("Bra",    chars_braille, "#CCCCFF"),
            ("Fle",    chars_flechas, "#FFE0AA"),
        ]
        for tab_name, chars, fg_hint in tabs:
            frame = tk.Frame(nb)
            nb.add(frame, text=tab_name)
            cvs = tk.Canvas(frame, bg="#111", bd=0, highlightthickness=0)
            vsb = ttk.Scrollbar(frame, orient="vertical", command=cvs.yview)
            cvs.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            cvs.pack(fill="both", expand=True)
            self._char_canvases[tab_name] = (cvs, chars, fg_hint)
            cvs.bind("<Configure>", lambda e, tn=tab_name: self._build_char_grid(tn))

        # ── Suscribir eventos ──────────────────────────────────────────────
        app.bus.on("color_changed",      lambda d: self.refresh(d["char"], d["fg"], d["bg"]))
        app.bus.on("color_mode_changed", lambda _: self.rebuild_palette())

    # ── Paleta de colores ──────────────────────────────────────────────────────

    def _build_palette_grid(self):
        for w in self._pal_frame.winfo_children():
            w.destroy()
        self._pal_cells.clear()

        svc = self.app.color_service
        palette   = svc.palette()
        count     = svc.count()
        is_256    = (svc.mode == "256")
        cell_size = 10 if is_256 else 20
        cols_per  = 16 if is_256 else 8
        hint      = "Clic=FG  Clic-der=BG  (xterm-256)" if is_256 else "Clic=FG  Clic-der=BG"

        for i, hex_color in enumerate(palette):
            r, c = divmod(i, cols_per)
            cell = tk.Canvas(self._pal_frame, width=cell_size, height=cell_size,
                             bg=hex_color, cursor="hand2", bd=0,
                             highlightthickness=1, highlightbackground="#222")
            cell.grid(row=r, column=c, padx=0, pady=0)
            cell.bind("<Button-1>", lambda e, idx=i: self.app.set_fg_color(idx))
            cell.bind("<Button-3>", lambda e, idx=i: self.app.set_bg_color(idx))
            self._pal_cells.append(cell)

        hint_rows = (count + cols_per - 1) // cols_per
        tk.Label(self._pal_frame, text=hint, font=("", 7)).grid(
            row=hint_rows, column=0, columnspan=cols_per, pady=2
        )

    def rebuild_palette(self):
        self._build_palette_grid()

    # ── Cuadrícula de caracteres ───────────────────────────────────────────────

    def _build_char_grid(self, tab_name):
        cvs, chars, fg_hint = self._char_canvases[tab_name]
        cvs.delete("all")
        if not chars:
            cvs.create_text(60, 30, text="(vacío)", fill="#888",
                            font=("Monospace", 9))
            return
        cw = max(cvs.winfo_width(), 80)
        cell_px = 14
        cols = max(1, cw // cell_px)
        font = ("Monospace", 9)
        for i, ch in enumerate(chars):
            r, c_idx = divmod(i, cols)
            x = c_idx * cell_px + cell_px // 2
            y = r * cell_px + cell_px // 2
            cid = cvs.create_text(x, y, text=ch, fill=fg_hint,
                                   font=font, anchor="center", tags="char")
            cvs.tag_bind(cid, "<Button-1>",
                         lambda e, cc=ch: self.app.set_fg_char(cc))
        total_rows = (len(chars) + cols - 1) // cols
        cvs.configure(scrollregion=(0, 0, cw, total_rows * cell_px + 4))

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self, fg_char, fg_color, bg_color):
        self._char_label.config(text=fg_char if fg_char != " " else "' '")
        svc = self.app.color_service
        self._fg_swatch.config(bg=svc.color(fg_color))
        self._bg_swatch.config(bg=svc.color(bg_color))
