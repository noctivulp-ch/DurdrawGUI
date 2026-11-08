"""Entrada de extremo a extremo: eventos Qt reales sobre la ventana completa.

Por qué: la entrada se repartió en drivers por dispositivo (ui/input/). Si un
driver deja de recibir o de traducir un evento, la app arranca y las pruebas
del modelo pasan, pero no se puede dibujar. Estas pruebas mandan eventos de
ratón, teclado y tableta a la App entera (offscreen) y comprueban el efecto en
el documento, que es lo que ve el usuario.
"""

import pytest
from PySide6.QtCore import Qt, QPointF, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QTabletEvent, QPointingDevice, QInputDevice
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def app(qapp):
    from ui.app import App
    w = App()
    w.show()
    QTest.qWaitForWindowExposed(w)
    qapp.processEvents()
    w.canvas_widget.setFocus()
    qapp.processEvents()
    yield w
    w._dirty = False
    w.close()
    w.deleteLater()
    qapp.processEvents()


def _cell(app, col, row):
    f = app.doc.current_frame()
    return f.content[row][col]


def _pos(app, col, row) -> QPointF:
    cv = app.canvas_widget
    x, y = cv.cell_to_screen(col, row)
    return QPointF(x + cv._cell_w / 2, y + cv._cell_h / 2)


def _mouse(app, etype, col, row, button, buttons=None, mods=Qt.KeyboardModifier.NoModifier):
    cv = app.canvas_widget
    p = _pos(app, col, row)
    if buttons is None:
        buttons = button if etype != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
    ev = QMouseEvent(etype, p, cv.mapToGlobal(p), button, buttons, mods)
    QApplication.sendEvent(cv, ev)


def _drag(app, cells, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
    (c0, r0), *rest = cells
    _mouse(app, QEvent.Type.MouseButtonPress, c0, r0, button, mods=mods)
    for c, r in rest:
        _mouse(app, QEvent.Type.MouseMove, c, r, Qt.MouseButton.NoButton, buttons=button, mods=mods)
    c, r = cells[-1]
    _mouse(app, QEvent.Type.MouseButtonRelease, c, r, button, mods=mods)


def _key(app, key, mods=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(app.canvas_widget, key, mods)
    QApplication.processEvents()


def test_clic_izquierdo_dibuja_con_el_lapiz(app):
    _drag(app, [(5, 5)])
    assert _cell(app, 5, 5) == app.fg_char


def test_arrastre_dibuja_una_linea_continua(app):
    _drag(app, [(2, 3), (9, 3)])
    assert all(_cell(app, c, 3) == app.fg_char for c in range(2, 10))


def test_clic_derecho_borra_y_restaura_la_herramienta(app):
    _drag(app, [(4, 4)])
    _drag(app, [(4, 4)], button=Qt.MouseButton.RightButton)
    assert _cell(app, 4, 4) == " "
    assert app.active_tool is app._tools["pencil"]


def test_alt_clic_recoge_el_color_sin_dibujar(app):
    app.set_fg_color(3)
    _drag(app, [(6, 6)])
    app.set_fg_color(9)
    _drag(app, [(6, 6)], mods=Qt.KeyboardModifier.AltModifier)
    assert app.fg_color == 3
    assert app.active_tool is app._tools["pencil"]


def test_boton_central_desplaza_el_lienzo_sin_dibujar(app):
    cv = app.canvas_widget
    cv.zoom_in(cv.width() // 2, cv.height() // 2)
    for _ in range(4):
        cv.zoom_in(cv.width() // 2, cv.height() // 2)
    QApplication.processEvents()
    cv.set_view(10, 5)
    before = (cv._view_col, cv._view_row)
    _drag(app, [(20, 10), (15, 10)], button=Qt.MouseButton.MiddleButton)
    assert (cv._view_col, cv._view_row) != before
    assert _cell(app, 20, 10) == " "


def test_atajo_de_herramienta_y_deshacer(app):
    _key(app, Qt.Key.Key_E)
    assert app.active_tool is app._tools["eraser"]
    _key(app, Qt.Key.Key_B)
    assert app.active_tool is app._tools["pencil"]
    _drag(app, [(7, 7)])
    assert _cell(app, 7, 7) == app.fg_char
    _key(app, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert _cell(app, 7, 7) == " "


def test_modo_cursor_de_teclado_dibuja_y_se_apaga(app):
    _key(app, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert app._kb_draw_mode is True
    cv = app.canvas_widget
    cv._kb_cursor = (1, 1)
    _key(app, Qt.Key.Key_Right)
    _key(app, Qt.Key.Key_Down)
    assert cv._kb_cursor == (2, 2)
    _key(app, Qt.Key.Key_Space)
    assert _cell(app, 2, 2) == app.fg_char
    # En el modo, B no cambia de herramienta: las acciones sueltas se desactivan.
    _key(app, Qt.Key.Key_B)
    _key(app, Qt.Key.Key_Q)
    assert _cell(app, 2, 2) == " "
    _key(app, Qt.Key.Key_Escape)
    assert app._kb_draw_mode is False


def test_ctrl_tab_alterna_una_sola_vez_por_pulsacion(app):
    _key(app, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert app._kb_draw_mode is True
    _key(app, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert app._kb_draw_mode is False


def _tablet(app, etype, col, row, buttons, button=Qt.MouseButton.LeftButton,
            pointer=QPointingDevice.PointerType.Pen):
    cv = app.canvas_widget
    p = _pos(app, col, row)
    dev = QPointingDevice("stylus-test", 9999, QInputDevice.DeviceType.Stylus, pointer,
                          QInputDevice.Capability.Position | QInputDevice.Capability.Pressure,
                          1, 3)
    ev = QTabletEvent(etype, dev, p, cv.mapToGlobal(p), 0.5, 0.0, 0.0, 0.0, 0.0, 0.0,
                      Qt.KeyboardModifier.NoModifier, button, buttons)
    QApplication.sendEvent(cv, ev)
    return ev


def test_tableta_dibuja_y_acepta_el_evento(app):
    L = Qt.MouseButton.LeftButton
    ev = _tablet(app, QEvent.Type.TabletPress, 10, 8, L)
    assert ev.isAccepted()
    _tablet(app, QEvent.Type.TabletMove, 12, 8, L)
    _tablet(app, QEvent.Type.TabletRelease, 12, 8, Qt.MouseButton.NoButton)
    assert all(_cell(app, c, 8) == app.fg_char for c in range(10, 13))


def test_boton_lateral_de_tableta_borra(app):
    _drag(app, [(11, 9)])
    both = Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
    _tablet(app, QEvent.Type.TabletPress, 11, 9, both)
    _tablet(app, QEvent.Type.TabletRelease, 11, 9, Qt.MouseButton.NoButton)
    assert _cell(app, 11, 9) == " "
    assert app.active_tool is app._tools["pencil"]


def test_captura_de_preferencias_no_admite_clic_en_acciones_de_teclado(qapp):
    from ui.preferences import ShortcutCapture
    dlg = ShortcutCapture(None, "B", mouse_only=False)
    QTest.mouseClick(dlg, Qt.MouseButton.RightButton, pos=QPoint(10, 10))
    assert dlg.captured is None
    dlg2 = ShortcutCapture(None, "", mouse_only=True)
    QTest.mouseClick(dlg2, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert dlg2.captured is None
    QTest.mouseClick(dlg2, Qt.MouseButton.RightButton, pos=QPoint(10, 10))
    assert dlg2.captured == "Mouse:RightButton"


def _dos_capas_con_seleccion(app):
    doc = app.doc
    doc.layers[0].frame_at(0).content[0][0] = "A"
    app.add_layer()                                  # la capa nueva queda activa
    doc.layers[1].frame_at(0).content[0][1] = "B"
    app.canvas_widget.render_frame()
    app.clipboard_mgr.sel_rect = (0, 0, 1, 0)


def test_ctrl_c_copia_solo_la_capa_activa(app):
    _dos_capas_con_seleccion(app)
    _key(app, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert [c[0] for c in app.clipboard_mgr.clipboard[0]] == [" ", "B"]


def test_ctrl_shift_c_copia_todas_las_capas_visibles(app):
    _dos_capas_con_seleccion(app)
    _key(app, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert [c[0] for c in app.clipboard_mgr.clipboard[0]] == ["A", "B"]
