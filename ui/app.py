import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Añadir raíz del proyecto al path para importaciones relativas
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.movie import Movie, Frame
from commands.commands import CommandHistory
import json, gzip
from tools.pencil     import PencilTool
from tools.eraser     import EraserTool
from tools.eyedropper import EyedropperTool
from ui.canvas     import AsciiCanvas
from ui.toolbar    import ToolBar
from ui.color_panel import ColorPanel
from ui.timeline   import Timeline
from ui.statusbar  import StatusBar

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
        self.fg_color  = 15   # blanco
        self.bg_color  = 0    # negro

        # ── Herramientas ───────────────────────────────────────────────────
        self._tools = {
            "pencil":     PencilTool(self),
            "eraser":     EraserTool(self),
            "eyedropper": EyedropperTool(self),
        }
        self.active_tool = self._tools["pencil"]

        # ── Layout ─────────────────────────────────────────────────────────
        self._build_menu()

        # Barra de estado (bottom fijo)
        self.statusbar = StatusBar(root)
        self.statusbar.pack(side="bottom", fill="x")

        # Timeline (encima del statusbar)
        self.timeline = Timeline(root, self, height=34)
        self.timeline.pack(side="bottom", fill="x")

        # Área principal: PanedWindow horizontal
        main_pane = ttk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)

        # Panel izquierdo: colores + paleta
        self.color_panel = ColorPanel(main_pane, self, width=160)
        main_pane.add(self.color_panel, weight=0)

        # Centro: canvas
        center = tk.Frame(main_pane)
        main_pane.add(center, weight=1)

        self.canvas_widget = AsciiCanvas(center, self)
        self.canvas_widget.pack(fill="both", expand=True)

        # Panel derecho: toolbar
        self.toolbar = ToolBar(main_pane, self, width=48)
        main_pane.add(self.toolbar, weight=0)

        # ── Atajos de teclado ──────────────────────────────────────────────
        root.bind("<Control-z>", lambda e: self.undo())
        root.bind("<Control-y>", lambda e: self.redo())
        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Control-o>", lambda e: self.open_file())
        root.bind("<Left>",      lambda e: self.prev_frame())
        root.bind("<Right>",     lambda e: self.next_frame())
        root.bind("<Home>",      lambda e: self.goto_first_frame())
        root.bind("<End>",       lambda e: self.goto_last_frame())
        root.bind("<Return>",    lambda e: self.timeline._toggle_play())
        root.bind("b",           lambda e: self.select_tool("pencil"))
        root.bind("e",           lambda e: self.select_tool("eraser"))
        root.bind("i",           lambda e: self.select_tool("eyedropper"))
        root.bind("x",           lambda e: self.swap_colors())

        # ── Render inicial ─────────────────────────────────────────────────
        root.update_idletasks()
        self.canvas_widget.render_frame(self.current_frame())
        self.toolbar.highlight("pencil")
        self._refresh_color_panel()
        self._refresh_timeline()

    # ── Menú ───────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Archivo", menu=fm)
        fm.add_command(label="Nuevo",          command=self.new_file,   accelerator="Ctrl+N")
        fm.add_command(label="Abrir…",         command=self.open_file,  accelerator="Ctrl+O")
        fm.add_command(label="Guardar…",       command=self.save,       accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label="Salir",          command=self.root.quit)

        em = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Edición", menu=em)
        em.add_command(label="Deshacer", command=self.undo, accelerator="Ctrl+Z")
        em.add_command(label="Rehacer",  command=self.redo, accelerator="Ctrl+Y")

        frm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Frame", menu=frm)
        frm.add_command(label="Nuevo frame",      command=self.add_frame,       accelerator="Alt+N")
        frm.add_command(label="Duplicar frame",   command=self.duplicate_frame, accelerator="Alt+D")
        frm.add_command(label="Eliminar frame",   command=self.delete_frame,    accelerator="Alt+C")
        frm.add_separator()
        frm.add_command(label="Anterior",         command=self.prev_frame,      accelerator="←")
        frm.add_command(label="Siguiente",        command=self.next_frame,      accelerator="→")

    # ── Acceso al modelo ───────────────────────────────────────────────────

    def current_frame(self):
        return self.movie.currentFrame

    # ── Gestión de herramientas ────────────────────────────────────────────

    def select_tool(self, name):
        if name not in self._tools:
            return
        self.active_tool = self._tools[name]
        self.toolbar.highlight(name)
        self.statusbar.set_tool(name)

    # ── Color y carácter activo ────────────────────────────────────────────

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

    # ── Navegación de frames ───────────────────────────────────────────────

    def _goto_frame(self, n):
        """n es 1-based."""
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
        self.movie   = Movie(_Opts(DEFAULT_W, DEFAULT_H))
        self.history = CommandHistory()
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
            # El primer frame vacío ya existe; lo reemplazamos
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
                cmap = fd["colorMap"]   # cmap[col][row]
                for col in range(w):
                    for row in range(h):
                        pair = cmap[col][row] if col < len(cmap) and row < len(cmap[col]) else [7, 0]
                        fr.newColorMap[row][col] = list(pair)
            mov.gotoFrame(1)
            self.movie   = mov
            self.history = CommandHistory()
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
                # colorMap[col][row] — formato esperado por durdraw
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
