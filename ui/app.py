import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.movie import Movie, Frame
from commands.commands import CommandHistory
import json, gzip
from tools.pencil     import PencilTool
from tools.eraser     import EraserTool
from tools.eyedropper import EyedropperTool
from tools.fill       import FillTool
from tools.selection  import SelectionTool
from ui.canvas      import AsciiCanvas
from ui.toolbar     import ToolBar
from ui.color_panel import ColorPanel
from ui.timeline    import Timeline
from ui.statusbar   import StatusBar
from ui.context_bar import ContextBar

DEFAULT_W = 80
DEFAULT_H = 24


class _Opts:
    def __init__(self, w, h):
        self.sizeX = w
        self.sizeY = h


class App:
    def __init__(self, root):
        self.root = root
        root.title("DurdrawGUI")
        root.minsize(900, 600)

        # ── Estado global ──────────────────────────────────────────────────
        self.movie     = Movie(_Opts(DEFAULT_W, DEFAULT_H))
        self.history   = CommandHistory()
        self.fg_char   = "@"
        self.fg_color  = 15
        self.bg_color  = 0

        # Selección y portapapeles
        self._sel_rect = None   # (c0, r0, c1, r1)
        self.clipboard = None   # lista de listas: [row][col] = (ch, fg, bg)

        # Rejilla visual
        self._show_grid = False

        # ── Herramientas ───────────────────────────────────────────────────
        self._tools = {
            "pencil":     PencilTool(self),
            "eraser":     EraserTool(self),
            "eyedropper": EyedropperTool(self),
            "fill":       FillTool(self),
            "selection":  SelectionTool(self),
        }
        self.active_tool = self._tools["pencil"]

        # ── Layout ─────────────────────────────────────────────────────────
        self._build_menu()

        self.statusbar = StatusBar(root)
        self.statusbar.pack(side="bottom", fill="x")

        self.timeline = Timeline(root, self, height=34)
        self.timeline.pack(side="bottom", fill="x")

        main_pane = ttk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)

        self.color_panel = ColorPanel(main_pane, self, width=160)
        main_pane.add(self.color_panel, weight=0)

        center = tk.Frame(main_pane)
        main_pane.add(center, weight=1)

        self.context_bar = ContextBar(center, self)
        self.context_bar.pack(side="top", fill="x")

        self.canvas_widget = AsciiCanvas(center, self)
        self.canvas_widget.pack(fill="both", expand=True)

        self.toolbar = ToolBar(main_pane, self, width=48)
        main_pane.add(self.toolbar, weight=0)

        # ── Atajos ─────────────────────────────────────────────────────────
        self._bind_keys()

        # ── Render inicial ─────────────────────────────────────────────────
        root.update_idletasks()
        self.canvas_widget.render_frame(self.current_frame())
        self.toolbar.highlight("pencil")
        self.context_bar.switch("pencil")
        self._refresh_color_panel()
        self._refresh_timeline()

    # ── Menú ───────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Archivo", menu=fm)
        fm.add_command(label="Nuevo",           command=self.new_file,    accelerator="Ctrl+N")
        fm.add_command(label="Abrir…",          command=self.open_file,   accelerator="Ctrl+O")
        fm.add_command(label="Guardar…",        command=self.save,        accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label="Exportar ANSI…",  command=self.export_ansi)
        fm.add_separator()
        fm.add_command(label="Salir",           command=self.root.quit)

        em = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Edición", menu=em)
        em.add_command(label="Deshacer",  command=self.undo,              accelerator="Ctrl+Z")
        em.add_command(label="Rehacer",   command=self.redo,              accelerator="Ctrl+Y")
        em.add_separator()
        em.add_command(label="Copiar",    command=self.copy_selection,    accelerator="Ctrl+C")
        em.add_command(label="Cortar",    command=self.cut_selection,     accelerator="Ctrl+X")
        em.add_command(label="Pegar",     command=self.paste_clipboard,   accelerator="Ctrl+V")
        em.add_separator()
        em.add_command(label="Seleccionar todo", command=self.select_all, accelerator="Ctrl+A")

        frm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Frame", menu=frm)
        frm.add_command(label="Nuevo frame",    command=self.add_frame,       accelerator="Alt+N")
        frm.add_command(label="Duplicar frame", command=self.duplicate_frame, accelerator="Alt+D")
        frm.add_command(label="Eliminar frame", command=self.delete_frame,    accelerator="Alt+C")
        frm.add_separator()
        frm.add_command(label="Anterior",       command=self.prev_frame,      accelerator="←")
        frm.add_command(label="Siguiente",      command=self.next_frame,      accelerator="→")

        vm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Vista", menu=vm)
        vm.add_command(label="Acercar",         command=self.zoom_in,    accelerator="Ctrl++")
        vm.add_command(label="Alejar",          command=self.zoom_out,   accelerator="Ctrl+-")
        vm.add_command(label="Zoom 1:1",        command=self.zoom_reset, accelerator="Ctrl+0")
        vm.add_separator()
        self._grid_var = tk.BooleanVar(value=False)
        vm.add_checkbutton(label="Mostrar rejilla", variable=self._grid_var,
                           command=self._toggle_grid)

    # ── Atajos de teclado ──────────────────────────────────────────────────

    def _bind_keys(self):
        r = self.root
        r.bind("<Control-z>",      lambda e: self.undo())
        r.bind("<Control-y>",      lambda e: self.redo())
        r.bind("<Control-s>",      lambda e: self.save())
        r.bind("<Control-o>",      lambda e: self.open_file())
        r.bind("<Control-n>",      lambda e: self.new_file())
        r.bind("<Control-c>",      lambda e: self.copy_selection())
        r.bind("<Control-x>",      lambda e: self.cut_selection())
        r.bind("<Control-v>",      lambda e: self.paste_clipboard())
        r.bind("<Control-a>",      lambda e: self.select_all())
        r.bind("<Control-equal>",  lambda e: self.zoom_in())
        r.bind("<Control-plus>",   lambda e: self.zoom_in())
        r.bind("<Control-minus>",  lambda e: self.zoom_out())
        r.bind("<Control-0>",      lambda e: self.zoom_reset())
        r.bind("<Left>",           lambda e: self.prev_frame())
        r.bind("<Right>",          lambda e: self.next_frame())
        r.bind("<Home>",           lambda e: self.goto_first_frame())
        r.bind("<End>",            lambda e: self.goto_last_frame())
        r.bind("<Return>",         lambda e: self.timeline._toggle_play())
        r.bind("<Delete>",         lambda e: self.clear_selection())
        r.bind("<Escape>",         lambda e: self.deselect())
        r.bind("b",                lambda e: self.select_tool("pencil"))
        r.bind("e",                lambda e: self.select_tool("eraser"))
        r.bind("i",                lambda e: self.select_tool("eyedropper"))
        r.bind("g",                lambda e: self.select_tool("fill"))
        r.bind("s",                lambda e: self.select_tool("selection"))
        r.bind("x",                lambda e: self.swap_colors())
        r.bind("<Alt-n>",          lambda e: self.add_frame())
        r.bind("<Alt-d>",          lambda e: self.duplicate_frame())
        r.bind("<Alt-c>",          lambda e: self.delete_frame())

    # ── Acceso al modelo ───────────────────────────────────────────────────

    def current_frame(self):
        return self.movie.currentFrame

    # ── Herramientas ───────────────────────────────────────────────────────

    def select_tool(self, name):
        if name not in self._tools:
            return
        self.active_tool = self._tools[name]
        self.toolbar.highlight(name)
        self.context_bar.switch(name)
        self.statusbar.set_tool(name)

    # ── Color y carácter ───────────────────────────────────────────────────

    def set_fg_color(self, idx):
        self.fg_color = idx
        self._refresh_color_panel()

    def set_bg_color(self, idx):
        self.bg_color = idx
        self._refresh_color_panel()

    def set_fg_char(self, ch):
        self.fg_char = ch
        self._refresh_color_panel()

    def set_active_colors(self, ch, fg, bg):
        self.fg_char  = ch
        self.fg_color = fg
        self.bg_color = bg
        self._refresh_color_panel()

    def swap_colors(self):
        self.fg_color, self.bg_color = self.bg_color, self.fg_color
        self._refresh_color_panel()

    def _refresh_color_panel(self):
        self.color_panel.refresh(self.fg_char, self.fg_color, self.bg_color)

    # ── Historial ──────────────────────────────────────────────────────────

    def undo(self):
        self.history.undo()

    def redo(self):
        self.history.redo()

    # ── Zoom ───────────────────────────────────────────────────────────────

    def zoom_in(self):
        self.canvas_widget.zoom_in()

    def zoom_out(self):
        self.canvas_widget.zoom_out()

    def zoom_reset(self):
        self.canvas_widget.zoom_reset()

    # ── Rejilla ────────────────────────────────────────────────────────────

    def _toggle_grid(self):
        self._show_grid = self._grid_var.get()
        self.canvas_widget.render_frame(self.current_frame())

    # ── Selección ──────────────────────────────────────────────────────────

    def set_selection_rect(self, c0, r0, c1, r1):
        self._sel_rect = (c0, r0, c1, r1) if c0 is not None else None

    def select_all(self):
        fr = self.current_frame()
        self.select_tool("selection")
        self.canvas_widget.set_selection(0, 0, fr.width - 1, fr.height - 1)
        self.set_selection_rect(0, 0, fr.width - 1, fr.height - 1)

    def deselect(self):
        if "selection" in self._tools:
            self._tools["selection"].deselect()
        self.set_selection_rect(None, None, None, None)

    def copy_selection(self):
        if not self._sel_rect:
            return
        c0, r0, c1, r1 = self._sel_rect
        frame = self.current_frame()
        self.clipboard = []
        for r in range(r0, r1 + 1):
            row_data = []
            for c in range(c0, c1 + 1):
                ch     = frame.content[r][c]
                fg, bg = frame.newColorMap[r][c]
                row_data.append((ch, fg, bg))
            self.clipboard.append(row_data)

    def cut_selection(self):
        if not self._sel_rect:
            return
        self.copy_selection()
        self.clear_selection()

    def paste_clipboard(self):
        if not self.clipboard:
            return
        frame = self.current_frame()
        # Pegar en la posición de inicio de la selección, o (0,0) si no hay selección
        if self._sel_rect:
            col0, row0 = self._sel_rect[0], self._sel_rect[1]
        else:
            col0, row0 = 0, 0

        snap_c = deepcopy(frame.content)
        snap_m = deepcopy(frame.newColorMap)
        clip   = deepcopy(self.clipboard)

        def _apply(content, colormap, clip_data, dc, dr):
            for ri, row_data in enumerate(clip_data):
                r = dr + ri
                if r >= frame.height:
                    break
                for ci, (ch, fg, bg) in enumerate(row_data):
                    c = dc + ci
                    if c >= frame.width:
                        break
                    content[r][c]    = ch
                    colormap[r][c]   = [fg, bg]

        _apply(frame.content, frame.newColorMap, clip, col0, row0)
        self.canvas_widget.render_frame(frame)

        new_c = deepcopy(frame.content)
        new_m = deepcopy(frame.newColorMap)

        def undo():
            frame.content     = deepcopy(snap_c)
            frame.newColorMap = deepcopy(snap_m)
            self.canvas_widget.render_frame(frame)

        def redo():
            frame.content     = deepcopy(new_c)
            frame.newColorMap = deepcopy(new_m)
            self.canvas_widget.render_frame(frame)

        self.history.push(undo, redo)

    def clear_selection(self):
        """Borrar el contenido de las celdas seleccionadas (espacio + color de fondo)."""
        if not self._sel_rect:
            return
        c0, r0, c1, r1 = self._sel_rect
        frame = self.current_frame()
        snap_c = deepcopy(frame.content)
        snap_m = deepcopy(frame.newColorMap)

        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                frame.content[r][c]    = " "
                frame.newColorMap[r][c] = [7, 0]
                self.canvas_widget.update_cell(c, r, " ", 7, 0)

        new_c = deepcopy(frame.content)
        new_m = deepcopy(frame.newColorMap)

        def undo():
            frame.content     = deepcopy(snap_c)
            frame.newColorMap = deepcopy(snap_m)
            self.canvas_widget.render_frame(frame)

        def redo():
            frame.content     = deepcopy(new_c)
            frame.newColorMap = deepcopy(new_m)
            self.canvas_widget.render_frame(frame)

        self.history.push(undo, redo)

    # ── Navegación de frames ───────────────────────────────────────────────

    def _goto_frame(self, n):
        total = self.movie.frameCount
        n = max(1, min(n, total))
        self.movie.currentFrameNumber = n
        self.movie.currentFrame = self.movie.frames[n - 1]
        self.canvas_widget.render_frame(self.current_frame())
        self._refresh_timeline()

    def prev_frame(self, wrap=False):
        n = self.movie.currentFrameNumber - 1
        if n < 1:
            n = self.movie.frameCount if wrap else 1
        self._goto_frame(n)

    def next_frame(self, wrap=False):
        n = self.movie.currentFrameNumber + 1
        if n > self.movie.frameCount:
            n = 1 if wrap else self.movie.frameCount
        self._goto_frame(n)

    def goto_first_frame(self):
        self._goto_frame(1)

    def goto_last_frame(self):
        self._goto_frame(self.movie.frameCount)

    def add_frame(self):
        self.movie.addEmptyFrame()
        self._goto_frame(self.movie.frameCount)

    def duplicate_frame(self):
        self.movie.duplicateCurrentFrame()
        self._goto_frame(self.movie.currentFrameNumber)

    def delete_frame(self):
        if self.movie.frameCount <= 1:
            return
        self.movie.deleteFrame()
        self._goto_frame(min(self.movie.currentFrameNumber,
                             self.movie.frameCount))

    def _refresh_timeline(self):
        cur   = self.movie.currentFrameNumber
        total = self.movie.frameCount
        self.timeline.update_display(cur, total)
        self.statusbar.set_frame(cur, total)

    # ── Archivo ────────────────────────────────────────────────────────────

    def new_file(self):
        self.timeline.stop_play()
        self.movie     = Movie(_Opts(DEFAULT_W, DEFAULT_H))
        self.history   = CommandHistory()
        self._sel_rect = None
        self.clipboard = None
        self.canvas_widget.render_frame(self.current_frame())
        self._refresh_timeline()
        self.root.title("DurdrawGUI")

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Archivos durdraw", "*.dur"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            opener = gzip.open if path.endswith(".dur") else open
            with opener(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            dm = data["DurMovie"]
            w, h = dm["sizeX"], dm["sizeY"]
            mov = Movie(_Opts(w, h))
            first = True
            for fd in dm["frames"]:
                if first:
                    fr = mov.frames[0]
                    first = False
                else:
                    mov.addEmptyFrame()
                    mov.nextFrame()
                    fr = mov.currentFrame
                for row_i, line in enumerate(fd["contents"]):
                    if row_i < h:
                        fr.content[row_i] = list(line.ljust(w))[:w]
                cmap = fd["colorMap"]
                for col in range(w):
                    for row in range(h):
                        pair = cmap[col][row] if col < len(cmap) and row < len(cmap[col]) else [7, 0]
                        fr.newColorMap[row][col] = list(pair)
            mov.gotoFrame(1)
            self.movie     = mov
            self.history   = CommandHistory()
            self._sel_rect = None
            self.clipboard = None
            self._goto_frame(1)
            self.root.title(f"DurdrawGUI — {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Error al abrir", str(exc))

    def save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".dur",
            filetypes=[("Archivos durdraw", "*.dur"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            mov = self.movie
            frames_data = []
            for fr in mov.frames:
                cmap = [[fr.newColorMap[row][col] for row in range(mov.sizeY)]
                        for col in range(mov.sizeX)]
                frames_data.append({
                    "frameNumber": len(frames_data) + 1,
                    "delay": getattr(fr, "delay", 1),
                    "contents": ["".join(fr.content[row]) for row in range(mov.sizeY)],
                    "colorMap": cmap,
                })
            payload = {
                "DurMovie": {
                    "formatVersion": 7,
                    "colorFormat": "16",
                    "preferredFont": "fixed",
                    "encoding": "utf-8",
                    "name": "",
                    "artist": "",
                    "framerate": 10,
                    "sizeX": mov.sizeX,
                    "sizeY": mov.sizeY,
                    "extra": None,
                    "frames": frames_data,
                }
            }
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(payload, f)
            self.root.title(f"DurdrawGUI — {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Error al guardar", str(exc))

    # ── Exportar ANSI ──────────────────────────────────────────────────────

    def export_ansi(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".ans",
            filetypes=[("Archivos ANSI", "*.ans"), ("Texto", "*.txt"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            frame  = self.current_frame()
            lines  = []
            for row in range(frame.height):
                parts = []
                last_fg, last_bg = -1, -1
                for col in range(frame.width):
                    ch     = frame.content[row][col]
                    fg, bg = frame.newColorMap[row][col]
                    if fg != last_fg or bg != last_bg:
                        parts.append(_ansi_color_seq(fg, bg))
                        last_fg, last_bg = fg, bg
                    parts.append(ch)
                parts.append("\x1b[0m")
                lines.append("".join(parts))
            output = "\r\n".join(lines)
            with open(path, "w", encoding="utf-8") as f:
                f.write(output)
            messagebox.showinfo("Exportado", f"ANSI guardado en:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))


# ── Helpers ANSI ───────────────────────────────────────────────────────────

# Mapeo de índice ANSI 16 → secuencias VT100
_FG_MAP = {
    0: "30", 1: "31", 2: "32", 3: "33",
    4: "34", 5: "35", 6: "36", 7: "37",
    8: "90", 9: "91", 10: "92", 11: "93",
    12: "94", 13: "95", 14: "96", 15: "97",
}
_BG_MAP = {
    0: "40", 1: "41", 2: "42", 3: "43",
    4: "44", 5: "45", 6: "46", 7: "47",
    8: "100", 9: "101", 10: "102", 11: "103",
    12: "104", 13: "105", 14: "106", 15: "107",
}


def _ansi_color_seq(fg, bg):
    f = _FG_MAP.get(fg % 16, "37")
    b = _BG_MAP.get(bg % 16, "40")
    return f"\x1b[{f};{b}m"
