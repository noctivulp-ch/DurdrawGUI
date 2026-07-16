"""
Gestión de selección y portapapeles.

Responsabilidad única: mantener el rectángulo de selección activo y el
contenido del portapapeles, y ejecutar las operaciones copiar/cortar/pegar/borrar.
App.py delega aquí; no contiene lógica de UI.
"""

from copy import deepcopy


class ClipboardManager:
    """Selección activa + portapapeles + operaciones de edición de región."""

    def __init__(self, app):
        self._app      = app
        self.sel_rect  = None   # (c0, r0, c1, r1) o None
        self.clipboard = None   # [[( ch, fg, bg ), …], …] o None

    # ── Selección ─────────────────────────────────────────────────────────────

    def set_rect(self, c0, r0, c1, r1):
        self.sel_rect = (c0, r0, c1, r1) if c0 is not None else None

    def reset(self):
        self.sel_rect  = None
        self.clipboard = None

    def select_all(self):
        doc = self._app.doc
        self._app.select_tool("selection")
        self._app.canvas_widget.set_selection(0, 0, doc.width - 1, doc.height - 1)
        self.sel_rect = (0, 0, doc.width - 1, doc.height - 1)

    def deselect(self):
        if "selection" in self._app._tools:
            self._app._tools["selection"].deselect()
        self.sel_rect = None

    # ── Copiar / cortar ───────────────────────────────────────────────────────

    def copy(self):
        if not self.sel_rect:
            return
        c0, r0, c1, r1 = self.sel_rect
        doc = self._app.doc
        self.clipboard = [
            [doc.composite_cell(c, r) for c in range(c0, c1 + 1)]
            for r in range(r0, r1 + 1)
        ]

    def cut(self):
        if not self.sel_rect:
            return
        self.copy()
        self.erase()

    # ── Pegar ─────────────────────────────────────────────────────────────────

    def paste(self):
        if not self.clipboard:
            return
        doc    = self._app.doc
        canvas = self._app.canvas_widget
        frame  = doc.current_frame()
        col0, row0 = (self.sel_rect[0], self.sel_rect[1]) if self.sel_rect else (0, 0)

        snap_c = deepcopy(frame.content)
        snap_m = deepcopy(frame.newColorMap)
        clip   = deepcopy(self.clipboard)

        for ri, row_data in enumerate(clip):
            r = row0 + ri
            if r >= doc.height:
                break
            for ci, (ch, fg, bg) in enumerate(row_data):
                c = col0 + ci
                if c >= doc.width:
                    break
                frame.content[r][c]    = ch
                frame.newColorMap[r][c] = [fg, bg]

        canvas.render_frame()

        new_c = deepcopy(frame.content)
        new_m = deepcopy(frame.newColorMap)

        def undo():
            frame.content     = deepcopy(snap_c)
            frame.newColorMap = deepcopy(snap_m)
            canvas.render_frame()

        def redo():
            frame.content     = deepcopy(new_c)
            frame.newColorMap = deepcopy(new_m)
            canvas.render_frame()

        self._app.history.push(undo, redo)

    # ── Borrar selección ──────────────────────────────────────────────────────

    def erase(self):
        """Borra el contenido de las celdas seleccionadas (espacio + colores por defecto)."""
        if not self.sel_rect:
            return
        c0, r0, c1, r1 = self.sel_rect
        doc    = self._app.doc
        canvas = self._app.canvas_widget
        frame  = doc.current_frame()

        snap_c = deepcopy(frame.content)
        snap_m = deepcopy(frame.newColorMap)

        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                frame.content[r][c]    = " "
                frame.newColorMap[r][c] = [7, 0]
                canvas.update_cell(c, r)

        new_c = deepcopy(frame.content)
        new_m = deepcopy(frame.newColorMap)

        def undo():
            frame.content     = deepcopy(snap_c)
            frame.newColorMap = deepcopy(snap_m)
            canvas.render_frame()

        def redo():
            frame.content     = deepcopy(new_c)
            frame.newColorMap = deepcopy(new_m)
            canvas.render_frame()

        self._app.history.push(undo, redo)
