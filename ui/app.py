import os

from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter,
                               QVBoxLayout, QMessageBox, QFileDialog)
from PySide6.QtCore    import Qt, QKeyCombination
from PySide6.QtGui     import QKeySequence, QShortcut, QCloseEvent

from core.document      import Document
from core.clipboard     import ClipboardManager
from core.color_service import ColorService
from core.event_bus     import EventBus
from core.tool_registry import create_all
from core.brush         import BrushLibrary
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

DEFAULT_W = 80
DEFAULT_H = 24


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        log.info("App Qt __init__ inicio")
        self.setWindowTitle("DurdrawGUI")
        self.resize(1200, 700)
        self.setMinimumSize(900, 600)

        # ── Servicios y modelo ─────────────────────────────────────────────
        self.bus           = EventBus()
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

        self.timeline = Timeline(central, self)
        main_layout.addWidget(self.timeline)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

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
        splitter.addWidget(right_w)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([160, 800, 240])

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
        mb = self.menuBar()

        fm = mb.addMenu("Archivo")
        fm.addAction("Nuevo lienzo…",    self.new_file,   QKeySequence("Ctrl+N"))
        fm.addAction("Abrir…",           self.open_file,  QKeySequence("Ctrl+O"))
        fm.addAction("Guardar…",         self.save,       QKeySequence("Ctrl+S"))
        fm.addSeparator()
        exp = fm.addMenu("Exportar")
        exp.addAction("ANSI…",           self.export_ansi)
        exp.addAction("PNG…",            self.export_png)
        exp.addAction("JPEG…",           self.export_jpeg)
        exp.addSeparator()
        exp.addAction("GIF animado…",    self.export_gif)
        exp.addAction("MP4…",            self.export_mp4)
        fm.addSeparator()
        fm.addAction("Salir",            self.close,      QKeySequence("Ctrl+Q"))

        em = mb.addMenu("Edición")
        em.addAction("Deshacer",         self.undo,               QKeySequence("Ctrl+Z"))
        em.addAction("Rehacer",          self.redo,               QKeySequence("Ctrl+Y"))
        em.addSeparator()
        em.addAction("Copiar",           self.copy_selection,     QKeySequence("Ctrl+C"))
        em.addAction("Cortar",           self.cut_selection,      QKeySequence("Ctrl+X"))
        em.addAction("Pegar",            self.paste_clipboard,    QKeySequence("Ctrl+V"))
        em.addSeparator()
        em.addAction("Seleccionar todo", self.select_all,         QKeySequence("Ctrl+A"))
        em.addAction("Deseleccionar",    self.deselect,           QKeySequence("Ctrl+D"))

        frm = mb.addMenu("Frame")
        frm.addAction("Nuevo frame",     self.add_frame,          QKeySequence("Alt+N"))
        frm.addAction("Duplicar frame",  self.duplicate_frame,    QKeySequence("Alt+D"))
        frm.addAction("Eliminar frame",  self.delete_frame,       QKeySequence("Alt+C"))
        frm.addSeparator()
        frm.addAction("Anterior",        self.prev_frame,         QKeySequence("Left"))
        frm.addAction("Siguiente",       self.next_frame,         QKeySequence("Right"))

        lm = mb.addMenu("Capas")
        lm.addAction("Nueva capa",       self.add_layer)
        lm.addAction("Eliminar capa",    self.delete_layer)
        lm.addSeparator()
        lm.addAction("Subir capa",       self.move_layer_up)
        lm.addAction("Bajar capa",       self.move_layer_down)

        vm = mb.addMenu("Vista")
        vm.addAction("Acercar",          self.zoom_in,    QKeySequence("Ctrl+="))
        vm.addAction("Alejar",           self.zoom_out,   QKeySequence("Ctrl+-"))
        vm.addAction("Zoom 1:1",         self.zoom_reset, QKeySequence("Ctrl+0"))

        self._grid_act = vm.addAction("Mostrar rejilla")
        self._grid_act.setCheckable(True)
        self._grid_act.triggered.connect(self._toggle_grid)

        vm.addSeparator()
        self._c256_act = vm.addAction("Modo 256 colores")
        self._c256_act.setCheckable(True)
        self._c256_act.triggered.connect(self._toggle_color_mode)

    # ── Atajos adicionales (teclas sueltas que el menú no puede registrar) ─

    def _bind_shortcuts(self):
        def sc(key, fn):
            s = QShortcut(QKeySequence(key), self)
            s.activated.connect(fn)

        sc("B",       lambda: self.select_tool("pencil"))
        sc("E",       lambda: self.select_tool("eraser"))
        sc("I",       lambda: self.select_tool("eyedropper"))
        sc("G",       lambda: self.select_tool("fill"))
        sc("S",       lambda: self.select_tool("selection"))
        sc("X",       self.swap_colors)
        sc("L",       lambda: self.select_tool("line"))
        sc("R",       lambda: self.select_tool("rect"))
        sc("O",       lambda: self.select_tool("ellipse"))
        sc("1",       self.zoom_reset)
        sc("Escape",  self.deselect)
        sc("Delete",  self.clear_selection)
        sc("Home",    self.goto_first_frame)
        sc("End",     self.goto_last_frame)
        sc("Return",  self.timeline._toggle_play)

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
        self.active_tool = self._tools[name]
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
        self.timeline.update_display(cur, total)
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
            self.history     = self._new_history()
            self._saved_path = path
            self._dirty      = False
            self.clipboard_mgr.reset()
            self.bus.emit("layers_changed", None)
            self._goto_frame(1)
            self.setWindowTitle(f"DurdrawGUI — {os.path.basename(path)}")
            log.info(f"open_file OK  {self.doc.width}×{self.doc.height}")
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
