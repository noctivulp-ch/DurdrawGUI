import os

from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter,
                               QVBoxLayout, QMessageBox, QFileDialog)
from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QKeySequence, QCloseEvent, QAction

from core.document      import Document
from core.clipboard     import ClipboardManager
from core.color_service import ColorService
from core.event_bus     import EventBus
from core.tool_registry import create_all
from core.brush         import BrushLibrary
from core.config        import AppConfig
from core.shortcuts     import ShortcutManager
from core.theme         import ThemeService
from commands.commands  import CommandHistory
import core.io          as doc_io
import core.log         as log

import tools.pencil       # noqa
import tools.eraser       # noqa
import tools.eyedropper   # noqa
import tools.fill         # noqa
import tools.selection    # noqa
import tools.line         # noqa
import tools.rect         # noqa
import tools.ellipse      # noqa

from ui.canvas      import AsciiCanvas
from ui.toolbar     import ToolBar
from ui.color_panel import ColorPanel
from ui.layer_panel import LayerPanel
from ui.context_bar import ContextBar
from ui.statusbar   import StatusBar
from ui.timeline    import Timeline
from ui.dialogs     import NewCanvasDialog
from ui.minimap     import MinimapOverlay
from ui.preferences import PreferencesDialog
from ui.char_panel  import CharPanel
from ui.about       import AboutDialog

DEFAULT_W = 80
DEFAULT_H = 24


class App(QMainWindow):
    # Acciones "de tecla suelta" que deben ceder ante el modo de dibujo por
    # teclado (namespace compartido — ver core/shortcuts.py). zoom_reset y
    # deselect combinan una tecla con modificador (permanece activa) con una
    # suelta: se manejan aparte en set_kb_draw_mode() en vez de deshabilitarse
    # por completo.
    _KB_MODE_GATED_ACTIONS = [
        "tool_pencil", "tool_eraser", "tool_eyedropper", "tool_fill",
        "tool_selection", "tool_line", "tool_rect", "tool_ellipse",
        "swap_colors", "minimap_toggle", "clear_selection",
        "frame_prev", "frame_next", "frame_first", "frame_last", "play_toggle",
    ]


    def __init__(self, open_file: str | None = None):
        super().__init__()
        self._open_file_at_start = open_file
        log.info("App Qt __init__ inicio")
        self.setWindowTitle("DurdrawGUI")
        self.resize(1200, 700)
        self.setMinimumSize(900, 600)

        # ── Configuración y atajos ─────────────────────────────────────────
        self.config       = AppConfig()
        self.shortcut_mgr = ShortcutManager()
        # bus se crea antes que theme_service porque éste emite eventos
        self.bus          = EventBus()
        self.theme_service = ThemeService(self.config, self.bus)
        self.theme_service.apply_current()
        self._actions: dict[str, QAction] = {}
        self._kb_draw_mode = False   # modo cursor de teclado (estado en canvas.py: _kb_cursor/_kb_target)

        # ── Servicios y modelo ─────────────────────────────────────────────
        self.color_service = ColorService(self.bus)
        self._dirty        = False
        self._saved_path   = None
        self.doc           = Document(DEFAULT_W, DEFAULT_H)
        self.history       = self._new_history()
        self.clipboard_mgr = ClipboardManager(self)
        self.brush_library = BrushLibrary()
        self.fg_char  = "@"
        self.fg_color = 15
        self.bg_color = 0
        self._show_grid = False

        # ── Herramientas ──────────────────────────────────────────────────
        self._tools      = create_all(self)
        self.active_tool = self._tools["pencil"]

        # ── Layout ────────────────────────────────────────────────────────
        self._build_menu()

        self.statusbar = StatusBar(self)
        self.setStatusBar(self.statusbar)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        self.timeline = Timeline(central, self)
        main_layout.addWidget(self.timeline)

        # Panel izquierdo: capas
        self.layer_panel = LayerPanel(splitter, self)
        splitter.addWidget(self.layer_panel)

        # Centro: barra de contexto + lienzo
        center_w = QWidget()
        center_layout = QVBoxLayout(center_w)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.context_bar = ContextBar(center_w, self)
        center_layout.addWidget(self.context_bar)
        self.canvas_widget = AsciiCanvas(center_w, self)
        center_layout.addWidget(self.canvas_widget, stretch=1)
        splitter.addWidget(center_w)

        # Panel derecho: herramientas + paleta
        right_w = QWidget()
        right_layout = QVBoxLayout(right_w)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        inner = QSplitter(Qt.Orientation.Horizontal)
        self.toolbar     = ToolBar(inner, self)
        self.color_panel = ColorPanel(inner, self)
        inner.addWidget(self.toolbar)
        inner.addWidget(self.color_panel)
        right_layout.addWidget(inner)
        self.char_panel = CharPanel(right_w, self)
        right_layout.addWidget(self.char_panel, stretch=1)
        splitter.addWidget(right_w)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([160, 800, 240])

        # ── Minimapa ──────────────────────────────────────────────────────
        self.minimap = MinimapOverlay(self.config)
        self.canvas_widget.minimap = self.minimap

        # ── Fuente del canvas (desde configuración) ───────────────────────
        font_family = self.config.get("canvas_font", "DejaVu Sans Mono")
        self.canvas_widget.set_font_family(font_family)
        doc_io.set_export_font_family(font_family)

        # ── Atajos ────────────────────────────────────────────────────────
        self._bind_shortcuts()

        # ── Render inicial ─────────────────────────────────────────────────
        self.canvas_widget.render_frame()
        self.toolbar.highlight("pencil")
        self.context_bar.switch("pencil")
        self._refresh_color_panel()
        self._refresh_timeline()
        log.info("App Qt inicializada")

        if self._open_file_at_start:
            QTimer.singleShot(0, lambda: self._load_file(self._open_file_at_start))

    # ── Menú ──────────────────────────────────────────────────────────────

    def _seqs(self, action_id: str) -> list[QKeySequence]:
        """Las 1-2 combinaciones asignadas a una acción, listas para QAction.setShortcuts."""
        return [QKeySequence(k) for k in self.shortcut_mgr.keys(action_id) if k]

    def _build_menu(self):
        acts = self._actions
        mb   = self.menuBar()

        def add(menu, label, action_id, fn):
            a = menu.addAction(label, fn)
            a.setShortcuts(self._seqs(action_id))
            acts[action_id] = a
            return a

        fm = mb.addMenu("Archivo")
        add(fm, "Nuevo lienzo…", "file_new",     self.new_file)
        add(fm, "Abrir…",        "file_open",    self.open_file)
        add(fm, "Guardar",       "file_save",    self.save)
        add(fm, "Guardar como…", "file_save_as", self.save_as)
        fm.addSeparator()
        exp = fm.addMenu("Exportar")
        add(exp, "ANSI…",        "export_ansi", self.export_ansi)
        add(exp, "PNG…",         "export_png",  self.export_png)
        add(exp, "JPEG…",        "export_jpeg", self.export_jpeg)
        exp.addSeparator()
        add(exp, "GIF animado…", "export_gif",  self.export_gif)
        add(exp, "MP4…",         "export_mp4",  self.export_mp4)
        fm.addSeparator()
        add(fm, "Salir", "file_quit", self.close)

        em = mb.addMenu("Edición")
        add(em, "Deshacer",         "undo",        self.undo)
        add(em, "Rehacer",          "redo",        self.redo)
        em.addSeparator()
        add(em, "Copiar",           "copy",        self.copy_selection)
        add(em, "Copiar fusionado", "copy_merged", self.copy_merged_selection)
        add(em, "Cortar",           "cut",         self.cut_selection)
        add(em, "Pegar",            "paste",       self.paste_clipboard)
        em.addSeparator()
        add(em, "Seleccionar todo", "select_all",  self.select_all)
        add(em, "Deseleccionar",    "deselect",    self.deselect)
        em.addSeparator()
        add(em, "Preferencias…", "preferences", self.open_preferences)

        frm = mb.addMenu("Frame")
        add(frm, "Nuevo frame",    "frame_new",       self.add_frame)
        add(frm, "Duplicar frame", "frame_duplicate", self.duplicate_frame)
        add(frm, "Eliminar frame", "frame_delete",    self.delete_frame)
        frm.addSeparator()
        add(frm, "Anterior",  "frame_prev", self.prev_frame)
        add(frm, "Siguiente", "frame_next", self.next_frame)

        lm = mb.addMenu("Capas")
        add(lm, "Nueva capa",    "layer_new",       self.add_layer)
        add(lm, "Eliminar capa", "layer_delete",    self.delete_layer)
        lm.addSeparator()
        add(lm, "Subir capa", "layer_move_up",   self.move_layer_up)
        add(lm, "Bajar capa", "layer_move_down", self.move_layer_down)

        vm = mb.addMenu("Vista")
        add(vm, "Acercar",  "zoom_in",    self.zoom_in)
        add(vm, "Alejar",   "zoom_out",   self.zoom_out)
        add(vm, "Zoom 1:1", "zoom_reset", self.zoom_reset)

        self._grid_act = vm.addAction("Mostrar rejilla")
        self._grid_act.setCheckable(True)
        self._grid_act.setShortcuts(self._seqs("toggle_grid"))
        self._grid_act.triggered.connect(self._toggle_grid)
        acts["toggle_grid"] = self._grid_act

        vm.addSeparator()
        self._c256_act = vm.addAction("Modo 256 colores")
        self._c256_act.setCheckable(True)
        self._c256_act.setShortcuts(self._seqs("toggle_color_mode"))
        self._c256_act.triggered.connect(self._toggle_color_mode)
        acts["toggle_color_mode"] = self._c256_act

        hm = mb.addMenu("Ayuda")
        hm.addAction("Acerca de…", self._show_about)

    def _show_about(self):
        AboutDialog(self).exec()

    # ── Atajos adicionales (herramientas y navegación, sin entrada de menú) ─

    def _bind_shortcuts(self):
        acts = self._actions

        def sc(action_id, fn):
            a = QAction(self)
            a.setShortcuts(self._seqs(action_id))
            a.triggered.connect(fn)
            self.addAction(a)
            acts[action_id] = a

        sc("tool_pencil",     lambda: self.select_tool("pencil"))
        sc("tool_eraser",     lambda: self.select_tool("eraser"))
        sc("tool_eyedropper", lambda: self.select_tool("eyedropper"))
        sc("tool_fill",       lambda: self.select_tool("fill"))
        sc("tool_selection",  lambda: self.select_tool("selection"))
        sc("tool_line",       lambda: self.select_tool("line"))
        sc("tool_rect",       lambda: self.select_tool("rect"))
        sc("tool_ellipse",    lambda: self.select_tool("ellipse"))
        sc("swap_colors",     self.swap_colors)
        sc("clear_selection", self.clear_selection)
        sc("frame_first",     self.goto_first_frame)
        sc("frame_last",      self.goto_last_frame)
        sc("play_toggle",     self.timeline._toggle_play)
        sc("center_view",     self.center_view)
        sc("minimap_toggle",  self._toggle_minimap)

        # kb_draw_toggle es especial: su primario (Ctrl+Tab, con modificador)
        # va como QAction de ventana normal — funciona sin importar qué
        # widget tenga el foco. Su secundario (Tab, tecla suelta) NO se
        # registra acá: Qt lo usaría para navegación de foco antes de que
        # llegue a un QAction; sigue andando vía AsciiCanvas.event()/
        # KeyboardInput cuando el canvas ya tiene el foco (ver canvas.py).
        kb_toggle = QAction(self)
        kb_toggle.setShortcut(QKeySequence(self.shortcut_mgr.key("kb_draw_toggle", 0)))
        kb_toggle.triggered.connect(self.canvas_widget.keyboard_input.toggle_draw_mode)
        self.addAction(kb_toggle)
        acts["kb_draw_toggle"] = kb_toggle

    def _rebuild_shortcuts(self):
        """Actualiza las combinaciones tras cambios en Preferencias (sin recrear objetos)."""
        for action_id, action in self._actions.items():
            if action_id == "kb_draw_toggle":
                action.setShortcut(QKeySequence(self.shortcut_mgr.key("kb_draw_toggle", 0)))
            else:
                action.setShortcuts(self._seqs(action_id))

    def set_kb_draw_mode(self, active: bool):
        """Activa/desactiva el modo cursor de teclado. Lo llama AsciiCanvas al
        detectar kb_draw_toggle/Escape. Mientras está activo, las acciones de
        tecla suelta (herramientas, navegación de frames…) se deshabilitan
        para que el canvas pueda interpretar esas mismas teclas como
        movimiento/dibujo — ver _KB_MODE_GATED_ACTIONS."""
        if active == self._kb_draw_mode:
            return
        log.info(f"kb_draw_mode → {'ON' if active else 'OFF'}")
        self._kb_draw_mode = active
        for action_id in self._KB_MODE_GATED_ACTIONS:
            self._actions[action_id].setEnabled(not active)
        if active:
            self._actions["zoom_reset"].setShortcuts(
                [QKeySequence(self.shortcut_mgr.key("zoom_reset", 0))])
            self._actions["deselect"].setShortcuts(
                [QKeySequence(self.shortcut_mgr.key("deselect", 0))])
            self.statusbar.showMessage("Modo cursor de teclado activado (Esc para salir)", 3000)
        else:
            self._rebuild_shortcuts()
            self.statusbar.showMessage("Modo cursor de teclado desactivado", 2000)
        self.canvas_widget.update()

    # ── Preferencias ──────────────────────────────────────────────────────

    def open_preferences(self):
        def on_accept():
            self.shortcut_mgr.save()
            self.config.save()
            self._rebuild_shortcuts()
            self.theme_service.apply(self.config.get("theme", "dark"))
            font_family = self.config.get("canvas_font", "DejaVu Sans Mono")
            self.canvas_widget.set_font_family(font_family)
            doc_io.set_export_font_family(font_family)

        dlg = PreferencesDialog(self, self.shortcut_mgr, self.config,
                                on_accept=on_accept)
        dlg.exec()

    # ── Vista ─────────────────────────────────────────────────────────────

    def center_view(self):
        self.canvas_widget.center_view()

    def _toggle_minimap(self):
        self.minimap.toggle()
        self.canvas_widget.update()

    # ── closeEvent (WM kill, Ctrl+Q, niri kill — todo pasa por aquí) ──────

    def closeEvent(self, event: QCloseEvent):
        log.info("closeEvent recibido")
        if self._confirm_discard():
            log.info("closeEvent  aceptado → cerrar")
            event.accept()
        else:
            log.info("closeEvent  cancelado por el usuario")
            event.ignore()

    # ── Dirty tracking ────────────────────────────────────────────────────

    def _new_history(self):
        return CommandHistory(on_change=self._mark_dirty)

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            base = os.path.basename(self._saved_path) if self._saved_path else "Sin título"
            self.setWindowTitle(f"DurdrawGUI — {base} *")

    def _clear_dirty(self):
        self._dirty = False
        base = os.path.basename(self._saved_path) if self._saved_path else "Sin título"
        self.setWindowTitle(f"DurdrawGUI — {base}")

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        resp = QMessageBox.question(
            self, "Cambios sin guardar",
            "El lienzo tiene cambios sin guardar.\n¿Descartar y continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel,
        )
        return resp == QMessageBox.StandardButton.Yes

    # ── Propiedades que tools/ necesitan ──────────────────────────────────

    def current_frame(self):
        return self.doc.current_frame()

    @property
    def active_brush(self):
        cb   = getattr(self, "context_bar", None)
        name = cb.active_brush_name if cb else "Punto 1×1"
        return self.brush_library.get(name)

    @property
    def _sel_rect(self):
        return self.clipboard_mgr.sel_rect

    @property
    def clipboard(self):
        return self.clipboard_mgr.clipboard

    @property
    def color_mode(self):
        return self.color_service.mode

    # ── Herramientas ──────────────────────────────────────────────────────

    def select_tool(self, name: str):
        if name not in self._tools:
            return
        prev = getattr(self.active_tool, "name", "?")
        self.active_tool = self._tools[name]
        log.debug(f"select_tool  {prev} → {name}")
        self.toolbar.highlight(name)
        self.context_bar.switch(name)
        self.statusbar.set_tool(name)

    # ── Color ──────────────────────────────────────────────────────────────

    def set_fg_color(self, idx: int):
        self.fg_color = idx
        self._refresh_color_panel()

    def set_bg_color(self, idx: int):
        self.bg_color = idx
        self._refresh_color_panel()

    def set_fg_char(self, ch: str):
        self.fg_char = ch

    def set_active_colors(self, ch, fg, bg):
        self.fg_char = ch; self.fg_color = fg; self.bg_color = bg
        self._refresh_color_panel()

    def swap_colors(self):
        self.fg_color, self.bg_color = self.bg_color, self.fg_color
        self._refresh_color_panel()

    def _refresh_color_panel(self):
        self.bus.emit("color_changed", {
            "fg": self.fg_color, "bg": self.bg_color, "char": self.fg_char,
        })

    # ── Historial ─────────────────────────────────────────────────────────

    # undo/redo restauran datos en el objeto frame capturado al crear el comando.
    # Si el usuario navegó a otro frame antes de deshacer, el caché compuesto del
    # frame editado quedaría obsoleto (la navegación lo dejó guardado): invalidamos
    # todos los frames para forzar recomposición al revisitarlos.
    def undo(self):
        self.history.undo()
        self.canvas_widget.invalidate_all_frames()
        self.canvas_widget.render_frame()

    def redo(self):
        self.history.redo()
        self.canvas_widget.invalidate_all_frames()
        self.canvas_widget.render_frame()

    # ── Zoom ──────────────────────────────────────────────────────────────

    def zoom_in(self, mx=None, my=None):   self.canvas_widget.zoom_in(mx, my)
    def zoom_out(self, mx=None, my=None):  self.canvas_widget.zoom_out(mx, my)
    def zoom_reset(self):                  self.canvas_widget.zoom_reset()

    # ── Rejilla / modo color ───────────────────────────────────────────────

    def _toggle_grid(self):
        self._show_grid = self._grid_act.isChecked()
        self.canvas_widget.render_frame()

    def _toggle_color_mode(self):
        mode = "256" if self._c256_act.isChecked() else "16"
        self._set_color_mode(mode)

    def _set_color_mode(self, mode: str, *, reset_colors: bool = False) -> bool:
        """Sincroniza doc.color_format + ColorService + checkbox + UI.

        Subir a 256 siempre es seguro (los índices 0-15 son idénticos en ambas
        paletas). Bajar a 16 es destructivo si el documento o los colores
        fg/bg activos usan la paleta extendida (>15) — el índice se
        reinterpretaría en una paleta de solo 16 entradas al pintar/exportar,
        y `ColorPanel` puede reventar con IndexError. Se bloquea ese caso.

        reset_colors=True omite el chequeo reseteando fg/bg a valores válidos
        en cualquier paleta (15/0) — usado al crear o abrir un documento,
        donde no hay nada previo que preservar.
        """
        if reset_colors:
            self.fg_color, self.bg_color = 15, 0
        elif mode == "16":
            unsafe = (self.doc.color_format == "256" and self.doc.has_extended_colors()) \
                     or self.fg_color > 15 or self.bg_color > 15
            if unsafe:
                QMessageBox.warning(
                    self, "No se puede bajar a 16 colores",
                    "El lienzo tiene celdas pintadas o colores activos fuera "
                    "del rango de 16 colores (paleta extendida de 256).\n"
                    "Reduce esos colores manualmente antes de cambiar de modo."
                )
                self._c256_act.setChecked(True)
                return False

        self.doc.color_format = mode
        self.color_service.set_mode(mode)
        self._c256_act.setChecked(mode == "256")
        self.color_panel.rebuild_palette()
        self._refresh_color_panel()
        self.canvas_widget.invalidate_all_frames()
        self.canvas_widget.render_frame()
        self.minimap.invalidate()
        return True

    # ── Selección ──────────────────────────────────────────────────────────

    def set_selection_rect(self, c0, r0, c1, r1):
        self.clipboard_mgr.set_rect(c0, r0, c1, r1)

    def select_all(self):     self.clipboard_mgr.select_all()
    def deselect(self):       self.clipboard_mgr.deselect()
    def copy_selection(self): self.clipboard_mgr.copy()
    def copy_merged_selection(self): self.clipboard_mgr.copy_merged()
    def cut_selection(self):  self.clipboard_mgr.cut()
    def paste_clipboard(self):
        if not self.clipboard_mgr.paste():
            QMessageBox.warning(
                self, "No se puede pegar",
                "Lo copiado usa colores de la paleta extendida (256) y el "
                "lienzo actual está en modo 16 colores.\n"
                "Cambia el lienzo a 256 colores para pegarlo sin pérdida."
            )
    def clear_selection(self):self.clipboard_mgr.erase()

    # ── Navegación de frames ───────────────────────────────────────────────

    def _goto_frame(self, n: int):
        self.doc.goto_frame(n)
        self.canvas_widget.render_frame()
        self._refresh_timeline()

    def prev_frame(self, wrap=False):
        n = self.doc.currentFrameNumber - 1
        if n < 1: n = self.doc.frameCount if wrap else 1
        self._goto_frame(n)

    def next_frame(self, wrap=False):
        n = self.doc.currentFrameNumber + 1
        if n > self.doc.frameCount: n = 1 if wrap else self.doc.frameCount
        self._goto_frame(n)

    def goto_first_frame(self): self._goto_frame(1)
    def goto_last_frame(self):  self._goto_frame(self.doc.frameCount)

    # Las cachés del lienzo van por índice de frame: insertar o borrar uno
    # desplaza los índices, así que se avisa con "frames_changed".
    def add_frame(self):
        self.doc.add_empty_frame()
        self.bus.emit("frames_changed", None)
        self._goto_frame(self.doc.frameCount)

    def duplicate_frame(self):
        self.doc.duplicate_current_frame()
        self.bus.emit("frames_changed", None)
        self._refresh_timeline()
        self.canvas_widget.render_frame()

    def delete_frame(self):
        self.doc.delete_frame()
        self.bus.emit("frames_changed", None)
        self._goto_frame(self.doc.currentFrameNumber)

    def _refresh_timeline(self):
        cur   = self.doc.currentFrameNumber
        total = self.doc.frameCount
        self.statusbar.set_frame(cur, total)

    # ── Capas ──────────────────────────────────────────────────────────────

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

    # ── Archivo ────────────────────────────────────────────────────────────

    def new_file(self):
        log.info("new_file inicio")
        if not self._confirm_discard():
            return
        dlg = NewCanvasDialog(self,
                              current_w=self.doc.width,
                              current_h=self.doc.height,
                              current_mode=self.color_service.mode)
        if dlg.exec() != NewCanvasDialog.DialogCode.Accepted:
            log.info("new_file cancelado")
            return
        d = dlg.result_data
        w, h, mode = d["width"], d["height"], d["color_mode"]
        log.info(f"new_file creando {w}×{h} modo={mode}")
        self.timeline.stop_play()
        self.doc          = Document(w, h, color_format=mode)
        self.history      = self._new_history()
        self._saved_path  = None
        self._dirty       = False
        self.clipboard_mgr.reset()
        self._set_color_mode(mode, reset_colors=True)
        self.bus.emit("layers_changed", None)
        self.canvas_widget.render_frame()
        self._refresh_timeline()
        self.setWindowTitle("DurdrawGUI — Sin título")
        self.canvas_widget.center_view()
        log.info(f"new_file listo {w}×{h}")

    def open_file(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir", "",
            "Archivos DurdrawGUI (*.durg *.dur);;Todos (*.*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            self.doc         = doc_io.load(path)
            self._set_color_mode(self.doc.color_format, reset_colors=True)
            self.history     = self._new_history()
            self._saved_path = path
            self._dirty      = False
            self.clipboard_mgr.reset()
            self.bus.emit("layers_changed", None)
            self._goto_frame(1)
            self.setWindowTitle(f"DurdrawGUI — {os.path.basename(path)}")
            self.canvas_widget.center_view()
            log.info(f"open_file OK  {self.doc.width}×{self.doc.height}  color={self.doc.color_format}")
        except Exception as exc:
            log.error(f"open_file ERROR: {exc}")
            QMessageBox.critical(self, "Error al abrir", str(exc))

    def save(self):
        """Guardado rápido: reutiliza la ruta actual; si el lienzo es nuevo, pide una (= Guardar como)."""
        if self._saved_path:
            self._save_to(self._saved_path)
        else:
            self.save_as()

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", os.path.basename(self._saved_path or ""),
            "DurdrawGUI (*.durg);;durdraw (*.dur);;Todos (*.*)"
        )
        if not path:
            return
        self._save_to(path)

    def _save_to(self, path):
        try:
            doc_io.save(self.doc, path)
            self._saved_path = path
            self._clear_dirty()
            log.info(f"save OK  {path}")
        except Exception as exc:
            log.error(f"save ERROR: {exc}")
            QMessageBox.critical(self, "Error al guardar", str(exc))

    # ── Exportar ───────────────────────────────────────────────────────────

    def _export(self, title, filt, ext, fn, needs_frames=False):
        if needs_frames and self.doc.frameCount < 2:
            QMessageBox.warning(self, "Sin animación",
                                "Necesitas al menos 2 frames para exportar animaciones.")
            return
        path, _ = QFileDialog.getSaveFileName(self, title, f"export{ext}", filt)
        if not path:
            return
        try:
            fn(self.doc, path)
            QMessageBox.information(self, "Exportado", f"Guardado en:\n{path}")
        except ImportError as exc:
            QMessageBox.critical(self, "Dependencia faltante", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))

    def export_ansi(self):
        self._export("Exportar ANSI", "ANSI (*.ans);;Texto (*.txt)", ".ans", doc_io.export_ansi)
    def export_png(self):
        self._export("Exportar PNG",  "PNG (*.png)", ".png", doc_io.export_png)
    def export_jpeg(self):
        self._export("Exportar JPEG", "JPEG (*.jpg)", ".jpg", doc_io.export_jpeg)
    def export_gif(self):
        self._export("Exportar GIF",  "GIF (*.gif)", ".gif", doc_io.export_gif,  needs_frames=True)
    def export_mp4(self):
        self._export("Exportar MP4",  "MP4 (*.mp4)", ".mp4", doc_io.export_mp4,  needs_frames=True)
