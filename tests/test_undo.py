"""Deshacer y rehacer con cada herramienta, con una y con varias capas (Rev-1).

Por qué: los snapshots de deshacer comparten los pares [fg, bg] con el frame
en lugar de copiarlos (core/grid_copy.py). Eso es correcto mientras ninguna
herramienta modifique un par en su sitio. Si alguien lo hace, el snapshot
cambia a la vez que el frame y deshacer «restaura» el estado ya modificado sin
avisar. Aquí cada herramienta pinta, se deshace y se rehace, comparando con una
foto profunda del documento entero.
"""

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def app(qapp):
    from ui.app import App
    w = App()
    w.show()
    qapp.processEvents()
    yield w
    w._dirty = False
    w.close()


def _foto(doc):
    return [[(tuple(map(tuple, f.content)), tuple(tuple(map(tuple, r)) for r in f.newColorMap))
             for f in layer.frames] for layer in doc.layers]


def _usar(app, tool, a, b):
    app.select_tool(tool)
    t = app.active_tool
    t.on_start(*a, 1)
    t.on_drag(*b)
    t.on_end(*b, 1)


@pytest.mark.parametrize("tool,a,b", [
    ("pencil", (2, 2), (9, 5)),
    ("eraser", (3, 3), (6, 3)),
    ("fill", (20, 10), (20, 10)),
    ("line", (1, 1), (15, 8)),
    ("rect", (4, 4), (12, 9)),
    ("ellipse", (10, 5), (18, 11)),
])
def test_deshacer_restaura_tras_cada_herramienta(app, tool, a, b):
    _usar(app, "pencil", (0, 0), (30, 12))   # algo que borrar o rellenar alrededor
    app.set_fg_color(4)
    app.set_bg_color(2)
    antes = _foto(app.doc)
    _usar(app, tool, a, b)
    despues = _foto(app.doc)
    assert despues != antes, f"{tool} no cambió nada: la prueba no prueba nada"
    app.undo()
    assert _foto(app.doc) == antes
    app.redo()
    assert _foto(app.doc) == despues


def test_deshacer_con_varias_capas_vuelve_a_cada_una(app):
    doc = app.doc
    vacio = _foto(doc)
    _usar(app, "pencil", (1, 1), (8, 1))
    tras_capa1 = _foto(doc)
    app.add_layer() if hasattr(app, "add_layer") else doc.add_layer()
    app.bus.emit("layers_changed", None)
    con_capa2_vacia = _foto(doc)
    _usar(app, "rect", (2, 0), (6, 3))
    app.undo()
    assert _foto(doc) == con_capa2_vacia
    # La capa activa ahora es la 2, pero el siguiente deshacer es de la 1.
    app.undo()
    assert _foto(doc)[0] == vacio[0]
    app.redo()
    assert _foto(doc)[0] == tras_capa1[0]
