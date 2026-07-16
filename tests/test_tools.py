import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.line    import _bresenham
from tools.rect    import _rect_outline, _rect_fill
from tools.ellipse import _ellipse_outline, _ellipse_fill


# ── Bresenham ─────────────────────────────────────────────────────────────────

def test_bresenham_horizontal():
    pts = list(_bresenham(0, 0, 4, 0))
    assert pts == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]


def test_bresenham_vertical():
    pts = list(_bresenham(0, 0, 0, 3))
    assert pts == [(0, 0), (0, 1), (0, 2), (0, 3)]


def test_bresenham_single_point():
    pts = list(_bresenham(2, 3, 2, 3))
    assert pts == [(2, 3)]


def test_bresenham_diagonal():
    pts = list(_bresenham(0, 0, 3, 3))
    assert (0, 0) in pts
    assert (3, 3) in pts
    assert len(pts) == 4


def test_bresenham_reversed():
    fwd = list(_bresenham(0, 0, 5, 0))
    rev = list(_bresenham(5, 0, 0, 0))
    assert set(fwd) == set(rev)


# ── Rect ──────────────────────────────────────────────────────────────────────

def test_rect_outline_corners():
    pts = _rect_outline(0, 0, 3, 2)
    assert (0, 0) in pts
    assert (3, 0) in pts
    assert (0, 2) in pts
    assert (3, 2) in pts


def test_rect_outline_no_interior():
    pts = _rect_outline(0, 0, 4, 4)
    assert (2, 2) not in pts  # interior


def test_rect_outline_single_cell():
    pts = _rect_outline(2, 2, 2, 2)
    assert (2, 2) in pts


def test_rect_fill_all_cells():
    pts = set(_rect_fill(0, 0, 2, 2))
    assert len(pts) == 9
    assert (1, 1) in pts  # interior


def test_rect_fill_reversed_coords():
    pts = set(_rect_fill(3, 3, 0, 0))
    assert len(pts) == 16  # 4×4


# ── Ellipse ───────────────────────────────────────────────────────────────────

def test_ellipse_outline_single_point():
    pts = _ellipse_outline(2, 2, 2, 2)
    assert (2, 2) in pts


def test_ellipse_outline_contains_extremes():
    pts = _ellipse_outline(0, 0, 10, 4)
    # Extremos horizontales
    assert any(c == 0 for c, r in pts)
    assert any(c == 10 for c, r in pts)


def test_ellipse_fill_contains_center():
    pts = _ellipse_fill(0, 0, 10, 10)
    cx, cy = 5, 5
    assert (cx, cy) in pts


def test_ellipse_fill_more_than_outline():
    outline = _ellipse_outline(0, 0, 10, 8)
    fill    = _ellipse_fill(0, 0, 10, 8)
    assert len(fill) > len(outline)


# ── FillTool (flood fill) con mock de app ────────────────────────────────────

def test_flood_fill_paints_all():
    from copy import deepcopy
    from tools.fill import FillTool

    class _Canvas:
        def update_cell(self, *a): pass
        def render_frame(self, *a): pass

    class _History:
        def push(self, u, r): pass

    class _Frame:
        def __init__(self, w, h):
            self.width = w
            self.height = h
            self.content = [[" "] * w for _ in range(h)]
            self.newColorMap = [[[7, 0]] * w for _ in range(h)]

    class _App:
        fg_char = "X"
        fg_color = 1
        bg_color = 2
        canvas_widget = _Canvas()
        history = _History()
        _frame = _Frame(5, 5)
        def current_frame(self): return self._frame

    app = _App()
    FillTool(app).on_start(2, 2, 1)

    # Todo el canvas debe haber sido pintado con "X"
    for r in range(5):
        for c in range(5):
            assert app._frame.content[r][c] == "X"
            assert app._frame.newColorMap[r][c] == [1, 2]


def test_flood_fill_respects_boundary():
    from tools.fill import FillTool

    class _Canvas:
        def update_cell(self, *a): pass
        def render_frame(self, *a): pass

    class _History:
        def push(self, u, r): pass

    class _Frame:
        def __init__(self):
            self.width = 5
            self.height = 5
            self.content = [[" "] * 5 for _ in range(5)]
            self.newColorMap = [[[7, 0]] * 5 for _ in range(5)]

    class _App:
        fg_char = "X"
        fg_color = 1
        bg_color = 0
        canvas_widget = _Canvas()
        history = _History()
        _frame = _Frame()
        def current_frame(self): return self._frame

    app = _App()
    # Poner una barrera en la columna 2
    for r in range(5):
        app._frame.content[r][2] = "#"
        app._frame.newColorMap[r][2] = [3, 0]

    FillTool(app).on_start(0, 0, 1)  # rellenar lado izquierdo

    # Columnas 0 y 1 deben ser "X"
    for r in range(5):
        assert app._frame.content[r][0] == "X"
        assert app._frame.content[r][1] == "X"
    # Columnas 3 y 4 deben estar sin tocar
    for r in range(5):
        assert app._frame.content[r][3] == " "
        assert app._frame.content[r][4] == " "
