import os

from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter,
                               QVBoxLayout, QMessageBox, QFileDialog)
from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QKeySequence, QShortcut, QCloseEvent, QAction

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

DEFAULT_W = 80
DEFAULT_H = 24


class App(QMainWindow):
    def __init__(self):
        super().__init__()
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
        self._actions:       dict[str, QAction]   = {}
        self._shortcut_objs: dict[str, QShortcut] = {}

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
        self.canvas_widget.set_font_family(
            self.config.get("canvas_font", "DejaVu Sans Mono")
        )

        # ── Atajos ────────────────────────────────────────────────────────
        self._bind_shortcuts()

        # ── Render inicial ─────────────────────────────────────────────────
        self.canvas_widget.render_frame()
        self.toolbar.highlight("pencil")
        self.context_bar.switch("pencil")
        self._refresh_color_panel()
        self._refresh_timeline()
        log.info("App Qt inicializada")

    # ── Menú ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        sm   = self.shortcut_mgr
        acts = self._actions
        mb   = self.menuBar()

        def add(menu, label, action_id, fn):
            a = menu.addAction(label, fn, QKeySequence(sm.key(action_id)))
            acts[action_id] = a
            return a

        fm = mb.addMenu("Archivo")
        add(fm, "Nuevo lienzo…", "file_new",  self.new_file)
        add(fm, "Abrir…",        "file_open", self.open_file)
        add(fm, "Guardar…",      "file_save", self.save)
        fm.addSeparator()
        exp = fm.addMenu("Exportar")
        exp.addAction("ANSI…",        self.export_ansi)
        exp.addAction("PNG…",         self.export_png)
        exp.addAction("JPEG…",        self.export_jpeg)
        exp.addSeparator()
        exp.addAction("GIF animado…", self.export_gif)
        exp.addAction("MP4…",         self.export_mp4)
        fm.addSeparator()
        add(fm, "Salir", "file_quit", self.close)

        em = mb.addMenu("Edición")
        add(em, "Deshacer",         "undo",        self.undo)
        add(em, "Rehacer",          "redo",        self.redo)
        em.addSeparator()
        add(em, "Copiar",           "copy",        self.copy_selection)
        add(em, "Cortar",           "cut",         self.cut_selection)
        add(em, "Pegar",            "paste",       self.paste_clipboard)
        em.addSeparator()
        add(em, "Seleccionar todo", "select_all",  self.select_all)
        add(em, "Deseleccionar",    "deselect",    self.deselect)
        em.addSeparator()
        em.addAction("Preferencias…", self.open_preferences)

        frm = mb.addMenu("Frame")
        add(frm, "Nuevo frame",    "frame_new",       self.add_frame)
        add(frm, "Duplicar frame", "frame_duplicate", self.duplicate_frame)
        add(frm, "Eliminar frame", "frame_delete",    self.delete_frame)
        frm.addSeparator()
        add(frm, "Anterior",  "frame_prev", self.prev_frame)
        add(frm, "Siguiente", "frame_next", self.next_frame)

        lm = mb.addMenu("Capas")
        lm.addAction("Nueva capa",    self.add_layer)
        lm.addAction("Eliminar capa", self.delete_layer)
        lm.addSeparator()
        lm.addAction("Subir capa",    self.move_layer_up)
        lm.addAction("Bajar capa",    self.move_layer_down)

        vm = mb.addMenu("Vista")
        add(vm, "Acercar",  "zoom_in",    self.zoom_in)
        add(vm, "Alejar",   "zoom_out",   self.zoom_out)
        add(vm, "Zoom 1:1", "zoom_reset", self.zoom_reset)

        self._grid_act = vm.addAction("Mostrar rejilla")
        self._grid_act.setCheckable(True)
        self._grid_act.triggered.connect(self._toggle_grid)

        vm.addSeparator()
        self._c256_act = vm.addAction("Modo 256 colores")
        self._c256_act.setCheckable(True)
        self._c256_act.triggered.connect(self._toggle_color_mode)

    # ── Atajos adicionales (teclas sueltas que el menú no puede registrar) ─

    def _bind_shortcuts(self):
        sm   = self.shortcut_mgr
        objs = self._shortcut_objs

        def sc(action_id, fn):
            s = QShortcut(QKeySequence(sm.key(action_id)), self)
            s.activated.connect(fn)
            objs[action_id] = s

        sc("tool_pencil",     lambda: self.select_tool("pencil"))
        sc("tool_eraser",     lambda: self.select_tool("eraser"))
        sc("tool_eyedropper", lambda: self.select_tool("eyedropper"))
        sc("tool_fill",       lambda: self.select_tool("fill"))
        sc("tool_selection",  lambda: self.select_tool("selection"))
        sc("tool_line",       lambda: self.select_tool("line"))
        sc("tool_rect",       lambda: self.select_tool("rect"))
        sc("tool_ellipse",    lambda: self.select_tool("ellipse"))
        sc("swap_colors",     self.swap_colors)
        sc("zoom_reset_1",    self.zoom_reset)
        sc("redo_alt",        self.redo)
        sc("deselect_esc",    self.deselect)
        sc("clear_selection", self.clear_selection)
        sc("frame_first",     self.goto_first_frame)
        sc("frame_last",      self.goto_last_frame)
        sc("play_toggle",     self.timeline._toggle_play)
        sc("center_view",     self.center_view)
        sc("minimap_toggle",  self._toggle_minimap)

    def _rebuild_shortcuts(self):
        """Actualiza teclas tras cambios en Preferencias (sin recrear objetos)."""
        sm = self.shortcut_mgr
        for action_id, action in self._actions.items():
            action.setShortcut(QKeySequence(sm.key(action_id)))
        for action_id, shortcut in self._shortcut_objs.items():
            shortcut.setKey(QKeySequence(sm.key(action_id)))

    # ── Preferencias ──────────────────────────────────────────────────────

    def open_preferences(self):
        def on_accept():
            self.shortcut_mgr.save()
            self.config.save()
            self._rebuild_shortcuts()
            self.theme_service.apply(self.config.get("theme", "dark"))
            self.canvas_widget.set_font_family(
                self.config.get("canvas_font", "DejaVu Sans Mono")
            )

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

    def undo(self): self.history.undo()
    def redo(self): self.history.redo()

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
        self.color_service.set_mode(mode)
        self.color_panel.rebuild_palette()
        self._refresh_color_panel()

    # ── Selección ──────────────────────────────────────────────────────────

    def set_selection_rect(self, c0, r0, c1, r1):
        self.clipboard_mgr.set_rect(c0, r0, c1, r1)

    def select_all(self):     self.clipboard_mgr.select_all()
    def deselect(self):       self.clipboard_mgr.deselect()
    def copy_selection(self): self.clipboard_mgr.copy()
    def cut_selection(self):  self.clipboard_mgr.cut()
    def paste_clipboard(self):self.clipboard_mgr.paste()
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
        self.color_service.set_mode(mode)
        self._c256_act.setChecked(mode == "256")
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
        if not path:
            return
        try:
            self.doc         = doc_io.load(path)
            self.color_service.set_mode(self.doc.color_format)
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
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar", os.path.basename(self._saved_path or ""),
            "DurdrawGUI (*.durg);;durdraw (*.dur);;Todos (*.*)"
        )
        if not path:
            return
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
