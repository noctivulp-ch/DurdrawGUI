import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.movie import Movie, Frame


class _Opts:
    def __init__(self, w, h):
        self.sizeX = w
        self.sizeY = h


def test_initial_frame():
    mov = Movie(_Opts(10, 5))
    assert mov.frameCount == 1
    fr = mov.currentFrame
    assert fr.width == 10
    assert fr.height == 5


def test_initial_content_is_spaces():
    mov = Movie(_Opts(4, 3))
    fr = mov.currentFrame
    assert fr.content[0][0] == " "
    assert fr.content[2][3] == " "


def test_initial_colormap_default():
    mov = Movie(_Opts(4, 3))
    fr = mov.currentFrame
    fg, bg = fr.newColorMap[0][0]
    assert bg == 0                  # fondo negro
    assert fg in (7, 8, 15)        # gris claro o equivalente


def test_add_empty_frame():
    mov = Movie(_Opts(4, 4))
    mov.addEmptyFrame()
    assert mov.frameCount == 2


def test_colormap_write():
    mov = Movie(_Opts(5, 5))
    fr = mov.currentFrame
    fr.newColorMap[2][3] = [5, 3]
    assert fr.newColorMap[2][3] == [5, 3]
    assert fr.newColorMap[0][0][1] == 0    # fondo sin tocar


def test_duplicate_frame_copies_content():
    mov = Movie(_Opts(4, 4))
    fr = mov.currentFrame
    fr.content[0][0] = "X"
    fr.newColorMap[0][0] = [1, 2]
    mov.duplicateCurrentFrame()
    mov.nextFrame()
    fr2 = mov.currentFrame
    assert fr2.content[0][0] == "X"
    assert fr2.newColorMap[0][0] == [1, 2]


def test_duplicate_frame_is_independent():
    mov = Movie(_Opts(4, 4))
    mov.duplicateCurrentFrame()
    mov.nextFrame()
    fr2 = mov.currentFrame
    fr2.content[0][0] = "Y"
    mov.gotoFrame(1)
    assert mov.currentFrame.content[0][0] == " "  # frame 1 no cambió


def test_delete_frame_reduces_count():
    mov = Movie(_Opts(4, 4))
    mov.addEmptyFrame()
    assert mov.frameCount == 2
    mov.deleteFrame()
    assert mov.frameCount == 1
