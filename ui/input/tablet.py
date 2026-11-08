"""Driver de tableta — QTabletEvent nativo (posición, presión, inclinación,
tipo de puntero, botones), sin depender de que el driver externo remapee
botones a clics de mouse. Aceptar el evento (event.accept()) suprime el
QMouseEvent sintetizado que Qt generaría para el mismo trazo, así que este
driver es la única fuente de verdad para interacciones de lápiz.

Reroute de herramienta con el mismo binding configurable que usa el mouse
(mouse_erase/mouse_pick_color en Preferencias → Ratón y tableta) — un botón
lateral mapeado por el driver externo a "clic derecho" llega igual que un
clic derecho de mouse. pointerType Eraser (borrador de hardware real) sigue
andando aparte si el lápiz lo tiene."""

from PySide6.QtCore import QEvent
from PySide6.QtGui  import QPointingDevice

import core.log as log
from ui.input.base import InputDriver

_log_input = log.get("input")


class TabletInput(InputDriver):
    def __init__(self, canvas, app):
        super().__init__(canvas, app)
        self._active            = False
        self._saved_tool        = None
        self._panning           = False
        self._scroll_origin     = None
        self._scroll_view_orig  = None

    def event(self, ev) -> bool:
        et = ev.type()
        if et == QEvent.Type.TabletPress:
            self._press(ev)
        elif et == QEvent.Type.TabletMove:
            self._move(ev)
        elif et == QEvent.Type.TabletRelease:
            self._release(ev)
        else:
            return False   # proximidad u otro tipo — sin manejar por ahora
        ev.accept()
        return True

    def _reroute_for(self, ev):
        # pointerType Eraser = borrador de hardware real (nunca visto en la
        # práctica: casi todos los lápices son de una punta + botones
        # laterales). buttons() sí llega siempre — mismo binding
        # configurable (mouse_erase/mouse_pick_color) que usa el mouse.
        if ev.pointerType() == QPointingDevice.PointerType.Eraser:
            return self.app._tools["eraser"]
        if self.matches_mouse_buttons_mask("mouse_erase", ev.buttons()):
            return self.app._tools["eraser"]
        if self.matches_mouse_buttons_mask("mouse_pick_color", ev.buttons()):
            return self.app._tools["eyedropper"]
        return None

    def _press(self, ev):
        x, y = ev.position().x(), ev.position().y()

        # mouse_pan (mismo binding configurable que el mouse) — desplazar el
        # lienzo en vez de dibujar, mientras se sostiene el botón.
        if self.matches_mouse_button("mouse_pan", ev.button()) or \
                self.matches_mouse_buttons_mask("mouse_pan", ev.buttons()):
            self._panning          = True
            self._scroll_origin    = (x, y)
            self._scroll_view_orig = (int(self.canvas._view_col), int(self.canvas._view_row))
            _log_input.debug("tablet_press  pan_start")
            return

        col, row = self.canvas.screen_to_cell(x, y)
        reroute = self._reroute_for(ev)
        if reroute is not None:
            self._saved_tool     = self.app.active_tool
            self.app.active_tool = reroute
        self._active = True
        _log_input.debug(
            f"tablet_press  ({col},{row})  pointer={ev.pointerType()}  "
            f"pressure={ev.pressure():.3f}  tool={self.app.active_tool.name}"
        )
        self.app.active_tool.on_start(col, row, 1)

    def _move(self, ev):
        x, y = ev.position().x(), ev.position().y()
        if self._panning:
            ox, oy = self._scroll_origin
            dx = (x - ox) // self.canvas._cell_w
            dy = (y - oy) // self.canvas._cell_h
            self.canvas.set_view(self._scroll_view_orig[0] - dx,
                                 self._scroll_view_orig[1] - dy)
            return
        col, row = self.canvas.screen_to_cell(x, y)
        if self._active:
            self.canvas.update_cursor(col, row)
            self.app.active_tool.on_drag(col, row)
        else:
            self.canvas.update_cursor(col, row)   # hover: solo preview, no dibuja

    def _release(self, ev):
        if self._panning:
            self._panning = False
            return
        if not self._active:
            return
        col, row = self.canvas.screen_to_cell(ev.position().x(), ev.position().y())
        _log_input.debug(f"tablet_release  ({col},{row})")
        self.app.active_tool.on_end(col, row, 1)
        if self.canvas.minimap:
            self.canvas.minimap.invalidate()
            self.canvas.update()
        if self._saved_tool is not None:
            self.app.active_tool = self._saved_tool
            self._saved_tool     = None
        self._active = False
