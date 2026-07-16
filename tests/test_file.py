import sys
import os
import json
import gzip
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.movie import Movie


class _Opts:
    def __init__(self, w, h):
        self.sizeX = w
        self.sizeY = h


def _save(mov, path):
    frames_data = []
    for fr in mov.frames:
        cmap = [[fr.newColorMap[row][col] for row in range(mov.sizeY)]
                for col in range(mov.sizeX)]
        frames_data.append({
            "frameNumber": len(frames_data) + 1,
            "delay": 1,
            "contents": ["".join(fr.content[row]) for row in range(mov.sizeY)],
            "colorMap": cmap,
        })
    payload = {
        "DurMovie": {
            "formatVersion": 7,
            "colorFormat": "16",
            "preferredFont": "fixed",
            "encoding": "utf-8",
            "name": "", "artist": "",
            "framerate": 10,
            "sizeX": mov.sizeX,
            "sizeY": mov.sizeY,
            "extra": None,
            "frames": frames_data,
        }
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)


def _load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    dm = data["DurMovie"]
    w, h = dm["sizeX"], dm["sizeY"]
    mov = Movie(_Opts(w, h))
    first = True
    for fd in dm["frames"]:
        if first:
            fr = mov.frames[0]
            first = False
        else:
            mov.addEmptyFrame()
            mov.nextFrame()
            fr = mov.currentFrame
        for row_i, line in enumerate(fd["contents"]):
            if row_i < h:
                fr.content[row_i] = list(line.ljust(w))[:w]
        cmap = fd["colorMap"]
        for col in range(w):
            for row in range(h):
                pair = cmap[col][row] if col < len(cmap) and row < len(cmap[col]) else [7, 0]
                fr.newColorMap[row][col] = list(pair)
    mov.gotoFrame(1)
    return mov


def test_roundtrip_dimensions():
    mov = Movie(_Opts(10, 5))
    with tempfile.NamedTemporaryFile(suffix=".dur", delete=False) as f:
        path = f.name
    try:
        _save(mov, path)
        mov2 = _load(path)
        assert mov2.sizeX == 10
        assert mov2.sizeY == 5
    finally:
        os.unlink(path)


def test_roundtrip_content():
    mov = Movie(_Opts(10, 5))
    mov.currentFrame.content[0][0] = "H"
    mov.currentFrame.content[1][3] = "i"
    with tempfile.NamedTemporaryFile(suffix=".dur", delete=False) as f:
        path = f.name
    try:
        _save(mov, path)
        mov2 = _load(path)
        assert mov2.currentFrame.content[0][0] == "H"
        assert mov2.currentFrame.content[1][3] == "i"
        assert mov2.currentFrame.content[0][1] == " "
    finally:
        os.unlink(path)


def test_roundtrip_colormap():
    mov = Movie(_Opts(10, 5))
    mov.currentFrame.newColorMap[0][0] = [3, 1]
    mov.currentFrame.newColorMap[4][9] = [15, 8]
    with tempfile.NamedTemporaryFile(suffix=".dur", delete=False) as f:
        path = f.name
    try:
        _save(mov, path)
        mov2 = _load(path)
        assert mov2.currentFrame.newColorMap[0][0] == [3, 1]
        assert mov2.currentFrame.newColorMap[4][9] == [15, 8]
    finally:
        os.unlink(path)


def test_roundtrip_multiframe():
    mov = Movie(_Opts(4, 4))
    mov.currentFrame.content[0][0] = "A"
    mov.addEmptyFrame()
    mov.nextFrame()
    mov.currentFrame.content[0][0] = "B"
    with tempfile.NamedTemporaryFile(suffix=".dur", delete=False) as f:
        path = f.name
    try:
        _save(mov, path)
        mov2 = _load(path)
        assert mov2.frameCount == 2
        mov2.gotoFrame(1)
        assert mov2.currentFrame.content[0][0] == "A"
        mov2.nextFrame()
        assert mov2.currentFrame.content[0][0] == "B"
    finally:
        os.unlink(path)
