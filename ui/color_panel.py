import tkinter as tk
from tkinter import ttk
from ui.canvas import ANSI_COLORS

# Tabla ASCII imprimible (32-126 + algunos útiles)
_CHARS = [chr(c) for c in range(32, 127)] + list("░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■")


class ColorPanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bd=1, relief="raised", **kwargs)
        self.app = app

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

        # ── Paleta 16 colores ──────────────────────────────────────────────
        pal_frame = tk.LabelFrame(self, text="Paleta ANSI")
        pal_frame.pack(fill="x", padx=4, pady=4)

        self._pal_cells = []
        for i, hex_color in enumerate(ANSI_COLORS):
            r, c = divmod(i, 8)
            cell = tk.Canvas(pal_frame, width=20, height=20, bg=hex_color,
                             cursor="hand2", bd=0, highlightthickness=1,
                             highlightbackground="#333")
            cell.grid(row=r, column=c, padx=1, pady=1)
            cell.bind("<Button-1>", lambda e, idx=i: self.app.set_fg_color(idx))
            cell.bind("<Button-3>", lambda e, idx=i: self.app.set_bg_color(idx))
            self._pal_cells.append(cell)

        tk.Label(pal_frame, text="Clic=FG  Clic-der=BG",
                 font=("", 8)).grid(row=2, column=0, columnspan=8, pady=2)

        # ── Selector de carácter ───────────────────────────────────────────
        char_frame = tk.LabelFrame(self, text="Carácter")
        char_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._char_canvas = tk.Canvas(char_frame, bg="#111", bd=0,
                                      highlightthickness=0)
        vsb = ttk.Scrollbar(char_frame, orient="vertical",
                            command=self._char_canvas.yview)
        self._char_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._char_canvas.pack(fill="both", expand=True)

        self._build_char_grid()
        self._char_canvas.bind("<Configure>", lambda e: self._build_char_grid())

    def _build_char_grid(self):
        self._char_canvas.delete("all")
        cw = max(self._char_canvas.winfo_width(), 80)
        cols = max(1, cw // 16)
        font = ("Monospace", 10)
        for i, ch in enumerate(_CHARS):
            r, c = divmod(i, cols)
            x = c * 16 + 8
            y = r * 16 + 8
            cid = self._char_canvas.create_text(x, y, text=ch, fill="#EEE",
                                                font=font, anchor="center",
                                                tags="char")
            self._char_canvas.tag_bind(
                cid, "<Button-1>", lambda e, cc=ch: self.app.set_fg_char(cc)
            )
        total_rows = (len(_CHARS) + cols - 1) // cols
        self._char_canvas.configure(
            scrollregion=(0, 0, cw, total_rows * 16 + 4)
        )

    def refresh(self, fg_char, fg_color, bg_color):
        self._char_label.config(text=fg_char if fg_char != " " else "' '")
        self._fg_swatch.config(bg=ANSI_COLORS[fg_color % 16])
        self._bg_swatch.config(bg=ANSI_COLORS[bg_color % 16])
