import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.document      import Document
from core.clipboard     import ClipboardManager
import core.io          as doc_io
from commands.commands  import CommandHistory
from core.event_bus     import EventBus
from core.color_service import ColorService
from core.tool_registry import create_all
from core.brush         import BrushLibrary
import core.log         as log

# Importar herramientas para que @register se ejecute y las registren
import tools.pencil       # noqa: F401
import tools.eraser       # noqa: F401
import tools.eyedropper   # noqa: F401
import tools.fill         # noqa: F401
import tools.selection    # noqa: F401
import tools.line         # noqa: F401
import tools.rect         # noqa: F401
import tools.ellipse      # noqa: F401

from ui.canvas      import AsciiCanvas
from ui.toolbar     import ToolBar
from ui.color_panel import ColorPanel
from ui.layer_panel import LayerPanel
from ui.timeline    import Timeline
from ui.statusbar   import StatusBar
from ui.context_bar import ContextBar

DEFAULT_W = 80
DEFAULT_H = 24


class NewCanvasOverlay(tk.Frame):
    """Panel superpuesto para configurar el nuevo lienzo.

    Es un Frame normal colocado sobre el canvas con place(), sin Toplevel ni
    ventana X11 separada. Evita todos los problemas de grab/WM_DELETE_WINDOW
    con XWayland/niri.  on_done(result | None) se llama al confirmar/cancelar.
    """

    def __init__(self, container, current_w=DEFAULT_W, current_h=DEFAULT_H,
                 current_mode="16", on_done=None):
        super().__init__(container, bd=1, relief="solid",
                         bg="#2b2b2b", padx=20, pady=14)
        self._on_done = on_done

        def lbl(parent, text, **kw):
            return tk.Label(parent, text=text, bg="#2b2b2b", fg="#dddddd", **kw)

        lbl(self, "Nuevo lienzo", font=("TkDefaultFont", 11, "bold")).pack(pady=(0, 10))

        # ── Ancho ──────────────────────────────────────────────────────────
        row = tk.Frame(self, bg="#2b2b2b"); row.pack(fill="x", pady=3)
        lbl(row, "Ancho:", width=9, anchor="e").pack(side="left")
        self._w = tk.IntVar(value=current_w)
        tk.Spinbox(row, from_=10, to=500, textvariable=self._w,
                   width=7).pack(side="left", padx=(8, 0))
        lbl(row, "columnas", fg="#888888").pack(side="left", padx=4)

        # ── Alto ───────────────────────────────────────────────────────────
        row = tk.Frame(self, bg="#2b2b2b"); row.pack(fill="x", pady=3)
        lbl(row, "Alto:", width=9, anchor="e").pack(side="left")
        self._h = tk.IntVar(value=current_h)
        tk.Spinbox(row, from_=4, to=300, textvariable=self._h,
                   width=7).pack(side="left", padx=(8, 0))
        lbl(row, "filas", fg="#888888").pack(side="left", padx=4)

        # ── Modo de color ──────────────────────────────────────────────────
        row = tk.Frame(self, bg="#2b2b2b"); row.pack(fill="x", pady=3)
        lbl(row, "Colores:", width=9, anchor="e").pack(side="left")
        self._mode = tk.StringVar(value=current_mode)
        for val, txt in (("16", "16 ANSI"), ("256", "256 xterm")):
            tk.Radiobutton(row, text=txt, value=val, variable=self._mode,
                           bg="#2b2b2b", fg="#dddddd",
                           selectcolor="#444444",
                           activebackground="#2b2b2b",
                           activeforeground="#ffffff").pack(side="left", padx=(8, 4))

        # ── Botones ────────────────────────────────────────────────────────
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(10, 0))
        btn_row = tk.Frame(self, bg="#2b2b2b"); btn_row.pack(pady=(10, 2))
        tk.Button(btn_row, text="Crear lienzo", width=13,
                  command=self._ok).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancelar", width=10,
                  command=self._cancel).pack(side="left", padx=6)

        self.bind_all("<Return>", lambda e: self._ok())
        self.bind_all("<Escape>", lambda e: self._cancel())
        log.debug("NewCanvasOverlay  construido")

    def show_centered(self):
        """Colocar centrado sobre el container padre con place()."""
        self.update_idletasks()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        ow = self.winfo_reqwidth()
        oh = self.winfo_reqheight()
        x = max(0, (pw - ow) // 2)
        y = max(0, (ph - oh) // 2)
        log.debug(f"NewCanvasOverlay  place x={x} y={y} en contenedor {pw}×{ph}")
        self.place(x=x, y=y)
        self.lift()
        self.focus_set()

    def _dismiss(self, result):
        log.debug(f"NewCanvasOverlay._dismiss  result={result}")
        self.unbind_all("<Return>")
        self.unbind_all("<Escape>")
        self.place_forget()
        self.destroy()
        if self._on_done:
            self._on_done(result)

    def _cancel(self):
        log.debug("NewCanvasOverlay._cancel  llamado")
        self._dismiss(None)

    def _ok(self):
        log.debug("NewCanvasOverlay._ok  llamado")
        try:
            w = int(self._w.get())
            h = int(self._h.get())
        except (ValueError, tk.TclError) as exc:
            log.warning(f"NewCanvasOverlay._ok  valor inválido: {exc}")
            messagebox.showerror("Valor inválido",
                                 "Ancho y alto deben ser números enteros.")
            return
        if not (10 <= w <= 500) or not (4 <= h <= 300):
            log.warning(f"NewCanvasOverlay._ok  rango inválido: {w}×{h}")
            messagebox.showerror("Valor fuera de rango",
                                 "Ancho: 10–500  ·  Alto: 4–300")
            return
        log.info(f"NewCanvasOverlay  aceptado: {w}×{h} modo={self._mode.get()}")
        self._dismiss({"width": w, "height": h, "color_mode": self._mode.get()})


class App:
    def __init__(self, root):
        log.info("App.__init__ inicio")
        self.root = root
        root.title("DurdrawGUI")
        root.minsize(900, 600)
        # Cierre limpio desde el WM (botón X, atajo de teclado del compositor, etc.)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        log.debug("App  WM_DELETE_WINDOW registrado en root")

        # ── Bus y servicios ────────────────────────────────────────────────
        self.bus           = EventBus()
        self.color_service = ColorService(self.bus)

        # ── Documento activo ───────────────────────────────────────────────
        self._dirty        = False          # hay cambios sin guardar
        self._saved_path   = None           # último path guardado (None = sin título)
        self.doc           = Document(DEFAULT_W, DEFAULT_H)
        self.history       = self._new_history()
        self.clipboard_mgr = ClipboardManager(self)
        self.fg_char  = "@"
        self.fg_color = 15
        self.bg_color = 0

        # Rejilla visual
        self._show_grid = False

        # ── Herramientas (desde el registro) ──────────────────────────────
        self._tools      = create_all(self)
        self.active_tool = self._tools["pencil"]

        # ── Librería de pinceles (antes del layout para que ContextBar la use) ─
        self.brush_library = BrushLibrary()

        # ── Layout ─────────────────────────────────────────────────────────
        self._build_menu()

        self.statusbar = StatusBar(root)
        self.statusbar.pack(side="bottom", fill="x")

        self.timeline = Timeline(root, self, height=34)
        self.timeline.pack(side="bottom", fill="x")

        main_pane = ttk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)

        # Panel izquierdo: solo capas (delgado, como en Aseprite)
        self.layer_panel = LayerPanel(main_pane, self, width=160)
        main_pane.add(self.layer_panel, weight=0)

        # Centro: barra de contexto + lienzo (recibe todo el espacio disponible)
        center = tk.Frame(main_pane)
        main_pane.add(center, weight=1)

        self.context_bar = ContextBar(center, self)
        self.context_bar.pack(side="top", fill="x")

        self.canvas_widget = AsciiCanvas(center, self)
        self.canvas_widget.pack(fill="both", expand=True)

        # Panel derecho: herramientas (izq) + paleta de color (der), como en Aseprite
        right_frame = tk.Frame(main_pane)
        main_pane.add(right_frame, weight=0)

        self.toolbar = ToolBar(right_frame, self, width=48)
        self.toolbar.pack(side="left", fill="y")

        self.color_panel = ColorPanel(right_frame, self)
        self.color_panel.pack(side="left", fill="both", expand=True)

        # ── Atajos ─────────────────────────────────────────────────────────
        self._bind_keys()

        # ── Render inicial ─────────────────────────────────────────────────
        root.update_idletasks()
        self.canvas_widget.render_frame()
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
        fm.add_command(label="Nuevo lienzo…",   command=self.new_file,    accelerator="Ctrl+N")
        fm.add_command(label="Abrir…",          command=self.open_file,   accelerator="Ctrl+O")
        fm.add_command(label="Guardar…",        command=self.save,        accelerator="Ctrl+S")
        fm.add_separator()
        exp_m = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="Exportar", menu=exp_m)
        exp_m.add_command(label="ANSI…",              command=self.export_ansi)
        exp_m.add_command(label="PNG…",               command=self.export_png)
        exp_m.add_command(label="JPEG…",              command=self.export_jpeg)
        exp_m.add_separator()
        exp_m.add_command(label="GIF animado…",       command=self.export_gif)
        exp_m.add_command(label="MP4…",               command=self.export_mp4)
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
        em.add_command(label="Seleccionar todo",  command=self.select_all, accelerator="Ctrl+A")
        em.add_command(label="Deseleccionar",     command=self.deselect,   accelerator="Ctrl+D / Esc")

        frm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Frame", menu=frm)
        frm.add_command(label="Nuevo frame",    command=self.add_frame,       accelerator="Alt+N")
        frm.add_command(label="Duplicar frame", command=self.duplicate_frame, accelerator="Alt+D")
        frm.add_command(label="Eliminar frame", command=self.delete_frame,    accelerator="Alt+C")
        frm.add_separator()
        frm.add_command(label="Anterior",       command=self.prev_frame,      accelerator="←")
        frm.add_command(label="Siguiente",      command=self.next_frame,      accelerator="→")

        lm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Capas", menu=lm)
        lm.add_command(label="Nueva capa",       command=self.add_layer)
        lm.add_command(label="Eliminar capa",    command=self.delete_layer)
        lm.add_separator()
        lm.add_command(label="Subir capa",       command=self.move_layer_up)
        lm.add_command(label="Bajar capa",       command=self.move_layer_down)

        vm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Vista", menu=vm)
        vm.add_command(label="Acercar",         command=self.zoom_in,    accelerator="Ctrl++")
        vm.add_command(label="Alejar",          command=self.zoom_out,   accelerator="Ctrl+-")
        vm.add_command(label="Zoom 1:1 (100%)", command=self.zoom_reset, accelerator="1")
        vm.add_command(label="Zoom mínimo",     command=lambda: self._zoom_to_index(0), accelerator="~")
        vm.add_separator()
        self._grid_var = tk.BooleanVar(value=False)
        vm.add_checkbutton(label="Mostrar rejilla", variable=self._grid_var,
                           command=self._toggle_grid)
        vm.add_separator()
        self._color256_var = tk.BooleanVar(value=False)
        vm.add_checkbutton(label="Modo 256 colores", variable=self._color256_var,
                           command=self._toggle_color_mode)

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
        r.bind("1",  lambda e: self.canvas_widget.zoom_reset())
        r.bind("2",  lambda e: self._zoom_to_index(5))   # 16px ≈ 114%
        r.bind("3",  lambda e: self._zoom_to_index(6))   # 18px ≈ 129%
        r.bind("4",  lambda e: self._zoom_to_index(7))   # 20px ≈ 143%
        r.bind("5",  lambda e: self._zoom_to_index(8))   # 24px ≈ 171%
        r.bind("grave", lambda e: self._zoom_to_index(0))  # ~ = mínimo
        r.bind("<Control-d>",      lambda e: self.deselect())
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
        r.bind("l",                lambda e: self.select_tool("line"))
        r.bind("r",                lambda e: self.select_tool("rect"))
        r.bind("o",                lambda e: self.select_tool("ellipse"))
        r.bind("<Alt-n>",          lambda e: self.add_frame())
        r.bind("<Alt-d>",          lambda e: self.duplicate_frame())
        r.bind("<Alt-c>",          lambda e: self.delete_frame())

    # ── Acceso al modelo ───────────────────────────────────────────────────

    def current_frame(self):
        """Frame de la capa activa (para escritura por herramientas)."""
        return self.doc.current_frame()

    @property
    def active_brush(self):
        """Pincel activo según el contexto de la barra de herramientas."""
        cb = getattr(self, "context_bar", None)
        name = cb.active_brush_name if cb else "Punto 1×1"
        return self.brush_library.get(name)

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

    @property
    def color_mode(self):
        return self.color_service.mode

    def _refresh_color_panel(self):
        self.bus.emit("color_changed", {
            "fg": self.fg_color,
            "bg": self.bg_color,
            "char": self.fg_char,
        })

    # ── Historial ──────────────────────────────────────────────────────────

    def undo(self):
        self.history.undo()

    def redo(self):
        self.history.redo()

    # ── Zoom ───────────────────────────────────────────────────────────────

    def zoom_in(self, mouse_x=None, mouse_y=None):
        self.canvas_widget.zoom_in(mouse_x, mouse_y)

    def zoom_out(self, mouse_x=None, mouse_y=None):
        self.canvas_widget.zoom_out(mouse_x, mouse_y)

    def zoom_reset(self):
        self.canvas_widget.zoom_reset()

    def _zoom_to_index(self, idx):
        from ui.canvas import _ZOOM_STEPS
        while self.canvas_widget._zoom_idx < idx:
            self.canvas_widget.zoom_in()
        while self.canvas_widget._zoom_idx > idx:
            self.canvas_widget.zoom_out()

    # ── Rejilla ────────────────────────────────────────────────────────────

    def _toggle_grid(self):
        self._show_grid = self._grid_var.get()
        self.canvas_widget.render_frame()

    def _toggle_color_mode(self):
        mode = "256" if self._color256_var.get() else "16"
        self.color_service.set_mode(mode)
        self._refresh_color_panel()

    # ── Selección ──────────────────────────────────────────────────────────

    # Propiedades que canvas.py y herramientas acceden directamente
    @property
    def _sel_rect(self):
        return self.clipboard_mgr.sel_rect

    @property
    def clipboard(self):
        return self.clipboard_mgr.clipboard

    def set_selection_rect(self, c0, r0, c1, r1):
        self.clipboard_mgr.set_rect(c0, r0, c1, r1)

    def select_all(self):
        self.clipboard_mgr.select_all()

    def deselect(self):
        self.clipboard_mgr.deselect()

    def copy_selection(self):
        self.clipboard_mgr.copy()

    def cut_selection(self):
        self.clipboard_mgr.cut()

    def paste_clipboard(self):
        self.clipboard_mgr.paste()

    def clear_selection(self):
        self.clipboard_mgr.erase()

    # ── Navegación de frames ───────────────────────────────────────────────

    def _goto_frame(self, n):
        self.doc.goto_frame(n)
        self.canvas_widget.render_frame()
        self._refresh_timeline()

    def prev_frame(self, wrap=False):
        n = self.doc.currentFrameNumber - 1
        if n < 1:
            n = self.doc.frameCount if wrap else 1
        self._goto_frame(n)

    def next_frame(self, wrap=False):
        n = self.doc.currentFrameNumber + 1
        if n > self.doc.frameCount:
            n = 1 if wrap else self.doc.frameCount
        self._goto_frame(n)

    def goto_first_frame(self):
        self._goto_frame(1)

    def goto_last_frame(self):
        self._goto_frame(self.doc.frameCount)

    def add_frame(self):
        self.doc.add_empty_frame()
        self._goto_frame(self.doc.frameCount)

    def duplicate_frame(self):
        self.doc.duplicate_current_frame()
        self._refresh_timeline()
        self.canvas_widget.render_frame()

    def delete_frame(self):
        self.doc.delete_frame()
        self._goto_frame(self.doc.currentFrameNumber)

    def _refresh_timeline(self):
        cur   = self.doc.currentFrameNumber
        total = self.doc.frameCount
        self.timeline.update_display(cur, total)
        self.statusbar.set_frame(cur, total)

    # ── Gestión de capas ───────────────────────────────────────────────────

    def add_layer(self):
        self.doc.add_layer()
        self.bus.emit("layers_changed", None)
        self.canvas_widget.render_frame()

    def delete_layer(self):
        self.doc.delete_active_layer()
        self.bus.emit("layers_changed", None)
        self.canvas_widget.render_frame()

    def move_layer_up(self):
        idx = self.doc.active_layer_idx
        self.doc.move_layer(idx, idx + 1)
        self.bus.emit("layers_changed", None)
        self.canvas_widget.render_frame()

    def move_layer_down(self):
        idx = self.doc.active_layer_idx
        self.doc.move_layer(idx, idx - 1)
        self.bus.emit("layers_changed", None)
        self.canvas_widget.render_frame()

    # ── Cierre de la aplicación ────────────────────────────────────────────

    def _on_close(self):
        """Llamado cuando el WM pide cerrar la ventana principal."""
        log.info("_on_close  WM_DELETE_WINDOW recibido")
        if self._confirm_discard():
            log.info("_on_close  confirmado → root.destroy()")
            self.root.destroy()
        else:
            log.info("_on_close  cancelado por el usuario")

    # ── Tracking de cambios sin guardar ───────────────────────────────────

    def _new_history(self):
        return CommandHistory(on_change=self._mark_dirty)

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            base = os.path.basename(self._saved_path) if self._saved_path else "Sin título"
            self.root.title(f"DurdrawGUI — {base} *")

    def _clear_dirty(self):
        self._dirty = False
        base = os.path.basename(self._saved_path) if self._saved_path else "Sin título"
        self.root.title(f"DurdrawGUI — {base}")

    def _confirm_discard(self) -> bool:
        """Pregunta si descartar cambios sin guardar. Devuelve True si se puede continuar."""
        if not self._dirty:
            log.debug("_confirm_discard  no hay cambios → continuar")
            return True
        log.info("_confirm_discard  hay cambios sin guardar → mostrando diálogo")
        resp = messagebox.askyesnocancel(
            "Cambios sin guardar",
            "El lienzo actual tiene cambios sin guardar.\n"
            "¿Descartar los cambios y continuar?",
        )
        log.info(f"_confirm_discard  respuesta={resp}")
        if resp is True:
            return True
        return False

    # ── Archivo ────────────────────────────────────────────────────────────

    def new_file(self):
        log.info("new_file  inicio")
        if not self._confirm_discard():
            log.info("new_file  cancelado en confirm_discard")
            return
        log.debug("new_file  abriendo NewCanvasOverlay")

        def _apply(result):
            if result is None:
                log.info("new_file  cancelado")
                return
            w        = result["width"]
            h        = result["height"]
            new_mode = result["color_mode"]
            log.info(f"new_file  creando lienzo {w}×{h} modo={new_mode}")
            self.color_service.set_mode(new_mode)
            self._color256_var.set(new_mode == "256")
            self.timeline.stop_play()
            self.doc          = Document(w, h)
            self.history      = self._new_history()
            self._saved_path  = None
            self._dirty       = False
            self.clipboard_mgr.reset()
            self.color_panel.rebuild_palette()
            self.bus.emit("layers_changed", None)
            self.canvas_widget.render_frame()
            self._refresh_timeline()
            self._refresh_color_panel()
            self.root.title("DurdrawGUI — Sin título")
            log.info(f"new_file  listo — lienzo {w}×{h} creado")

        overlay = NewCanvasOverlay(
            self.canvas_widget,      # superpuesto sobre el canvas
            current_w=self.doc.width,
            current_h=self.doc.height,
            current_mode=self.color_service.mode,
            on_done=_apply,
        )
        overlay.show_centered()

    def open_file(self):
        log.info("open_file  inicio")
        if not self._confirm_discard():
            log.info("open_file  cancelado en confirm_discard")
            return
        path = filedialog.askopenfilename(
            filetypes=[
                ("Archivos DurdrawGUI", "*.durg *.dur"),
                ("Archivos durdraw", "*.dur"),
                ("Todos", "*.*"),
            ]
        )
        if not path:
            log.info("open_file  selección cancelada")
            return
        log.info(f"open_file  cargando '{path}'")
        try:
            self.doc         = doc_io.load(path)
            self.history     = self._new_history()
            self._saved_path = path
            self._dirty      = False
            self.clipboard_mgr.reset()
            self.bus.emit("layers_changed", None)
            self._goto_frame(1)
            self.root.title(f"DurdrawGUI — {os.path.basename(path)}")
            log.info(f"open_file  OK — {self.doc.width}×{self.doc.height}"
                     f" {self.doc.frameCount} frames {len(self.doc.layers)} capas")
        except Exception as exc:
            log.error(f"open_file  ERROR: {exc}")
            messagebox.showerror("Error al abrir", str(exc))

    def save(self):
        log.info("save  inicio")
        path = filedialog.asksaveasfilename(
            defaultextension=".durg",
            initialfile=os.path.basename(self._saved_path) if self._saved_path else "",
            filetypes=[
                ("Archivo DurdrawGUI (capas)", "*.durg"),
                ("Archivo durdraw (aplanado)", "*.dur"),
                ("Todos", "*.*"),
            ]
        )
        if not path:
            log.info("save  cancelado")
            return
        log.info(f"save  guardando en '{path}'")
        try:
            doc_io.save(self.doc, path)
            self._saved_path = path
            self._clear_dirty()
            log.info("save  OK")
        except Exception as exc:
            log.error(f"save  ERROR: {exc}")
            messagebox.showerror("Error al guardar", str(exc))

    # ── Exportar ───────────────────────────────────────────────────────────

    def export_ansi(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".ans",
            filetypes=[("Archivos ANSI", "*.ans"), ("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            doc_io.export_ansi(self.doc, path)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def export_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            doc_io.export_png(self.doc, path)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}")
        except ImportError as exc:
            messagebox.showerror("Dependencia faltante", str(exc))
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def export_jpeg(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg *.jpeg"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            doc_io.export_jpeg(self.doc, path)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}")
        except ImportError as exc:
            messagebox.showerror("Dependencia faltante", str(exc))
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def export_gif(self):
        if self.doc.frameCount < 2:
            messagebox.showwarning(
                "Sin animación",
                "El documento necesita al menos 2 frames para exportar como GIF animado.\n"
                "Añade frames desde el menú Frame → Nuevo frame.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("GIF", "*.gif"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            doc_io.export_gif(self.doc, path)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}")
        except ImportError as exc:
            messagebox.showerror("Dependencia faltante", str(exc))
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def export_mp4(self):
        if self.doc.frameCount < 2:
            messagebox.showwarning(
                "Sin animación",
                "El documento necesita al menos 2 frames para exportar como MP4.\n"
                "Añade frames desde el menú Frame → Nuevo frame.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            doc_io.export_mp4(self.doc, path)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}")
        except ImportError as exc:
            messagebox.showerror("Dependencia faltante", str(exc))
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))
