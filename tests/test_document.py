import sys
import os
import json
import gzip
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.document import Document
from core.io import to_durg, to_dur, from_durg, from_dur


def test_initial_single_layer():
    doc = Document(20, 10)
    assert len(doc.layers) == 1
    assert doc.layers[0].name == "Fondo"
    assert doc.frameCount == 1


def test_dimensions():
    doc = Document(30, 15)
    assert doc.width  == 30
    assert doc.height == 15
    assert doc.sizeX  == 30
    assert doc.sizeY  == 15


def test_current_frame_is_active_layer_frame():
    doc = Document(10, 5)
    doc.layers[0].frame_at(0).content[0][0] = "A"
    assert doc.current_frame().content[0][0] == "A"


def test_composite_single_layer():
    doc = Document(10, 5)
    doc.layers[0].frame_at(0).content[2][3] = "X"
    doc.layers[0].frame_at(0).newColorMap[2][3] = [1, 2]
    comp = doc.composite_frame()
    assert comp.content[2][3] == "X"
    assert comp.newColorMap[2][3] == [1, 2]


def test_transparent_cell_empty_space():
    doc = Document(10, 5)
    doc.add_layer()
    # Capa 0: "A" en (0,0) con bg!=0
    doc.layers[0].frame_at(0).content[0][0] = "A"
    doc.layers[0].frame_at(0).newColorMap[0][0] = [7, 1]
    # Capa 1: espacio con bg=0 → transparente, debe ver "A" de capa 0
    doc.layers[1].frame_at(0).content[0][0] = " "
    doc.layers[1].frame_at(0).newColorMap[0][0] = [7, 0]
    comp = doc.composite_frame()
    assert comp.content[0][0] == "A"


def test_upper_layer_overrides():
    doc = Document(10, 5)
    doc.add_layer()
    doc.layers[0].frame_at(0).content[0][0] = "A"
    doc.layers[1].frame_at(0).content[0][0] = "B"
    doc.layers[1].frame_at(0).newColorMap[0][0] = [7, 1]  # bg!=0 → opaco
    comp = doc.composite_frame()
    assert comp.content[0][0] == "B"


def test_invisible_layer_skipped():
    doc = Document(10, 5)
    doc.add_layer()
    doc.layers[0].frame_at(0).content[0][0] = "A"
    doc.layers[0].frame_at(0).newColorMap[0][0] = [7, 1]
    doc.layers[1].frame_at(0).content[0][0] = "B"
    doc.layers[1].frame_at(0).newColorMap[0][0] = [7, 2]
    doc.layers[1].visible = False
    comp = doc.composite_frame()
    assert comp.content[0][0] == "A"


def test_composite_cell():
    doc = Document(10, 5)
    doc.layers[0].frame_at(0).content[1][2] = "Z"
    doc.layers[0].frame_at(0).newColorMap[1][2] = [3, 4]
    ch, fg, bg = doc.composite_cell(2, 1)
    assert ch == "Z"
    assert fg == 3
    assert bg == 4


def test_add_layer_syncs_frames():
    doc = Document(10, 5)
    doc.add_empty_frame()
    doc.add_empty_frame()
    assert doc.frameCount == 3
    doc.add_layer()
    assert len(doc.layers[1].frames) == 3


def test_add_empty_frame_all_layers():
    doc = Document(10, 5)
    doc.add_layer()
    doc.add_empty_frame()
    assert doc.frameCount == 2
    assert len(doc.layers[0].frames) == 2
    assert len(doc.layers[1].frames) == 2


def test_duplicate_frame_advances_idx():
    doc = Document(10, 5)
    doc.layers[0].frame_at(0).content[0][0] = "D"
    doc.duplicate_current_frame()
    assert doc.currentFrameNumber == 2
    assert doc.frameCount == 2
    assert doc.current_frame().content[0][0] == "D"


def test_delete_frame_reduces_count():
    doc = Document(10, 5)
    doc.add_empty_frame()
    doc.add_empty_frame()
    assert doc.frameCount == 3
    doc.delete_frame()
    assert doc.frameCount == 2


def test_delete_last_frame_no_op():
    doc = Document(10, 5)
    doc.delete_frame()
    assert doc.frameCount == 1


def test_goto_frame_1based():
    doc = Document(10, 5)
    doc.add_empty_frame()
    doc.add_empty_frame()
    doc.goto_frame(3)
    assert doc.currentFrameNumber == 3
    doc.goto_frame(1)
    assert doc.currentFrameNumber == 1


def test_delete_active_layer_no_single():
    doc = Document(10, 5)
    doc.delete_active_layer()
    assert len(doc.layers) == 1


def test_set_active_layer():
    doc = Document(10, 5)
    doc.add_layer()
    doc.set_active_layer(0)
    assert doc.active_layer_idx == 0


def test_move_layer():
    doc = Document(10, 5)
    doc.add_layer(name="Capa 2")
    doc.add_layer(name="Capa 3")
    original_name = doc.layers[0].name
    doc.move_layer(0, 2)
    assert doc.layers[2].name == original_name


def test_round_trip_durg():
    doc = Document(8, 4)
    doc.layers[0].frame_at(0).content[0][0] = "X"
    doc.layers[0].frame_at(0).newColorMap[0][0] = [3, 1]
    doc.add_layer(name="Superior")
    doc.layers[1].frame_at(0).content[1][1] = "Y"

    payload = to_durg(doc)
    doc2 = from_durg(payload)
    assert len(doc2.layers) == 2
    assert doc2.layers[0].frame_at(0).content[0][0] == "X"
    assert doc2.layers[0].frame_at(0).newColorMap[0][0] == [3, 1]
    assert doc2.layers[1].name == "Superior"
    assert doc2.layers[1].frame_at(0).content[1][1] == "Y"


def test_round_trip_dur():
    doc = Document(8, 4)
    doc.layers[0].frame_at(0).content[0][0] = "A"
    doc.layers[0].frame_at(0).newColorMap[0][0] = [2, 0]

    payload = to_dur(doc)
    doc2 = from_dur(payload)
    assert doc2.layers[0].frame_at(0).content[0][0] == "A"


def test_composite_frame_idx_param():
    doc = Document(8, 4)
    doc.add_empty_frame()
    doc.goto_frame(2)
    doc.layers[0].frame_at(1).content[0][0] = "B"
    doc.goto_frame(1)
    comp = doc.composite_frame(frame_idx=1)
    assert comp.content[0][0] == "B"


def test_round_trip_durg_dos_capas_tres_frames_mismo_compuesto():
    """Rev-1: el compuesto de cada frame sobrevive a guardar y cargar .durg."""
    doc = Document(10, 5)
    doc.add_layer(name="Arriba")
    doc.add_empty_frame()
    doc.add_empty_frame()
    for fi in range(3):
        base, top = doc.layers[0].frame_at(fi), doc.layers[1].frame_at(fi)
        base.content[fi][fi] = "B"
        base.newColorMap[fi][fi] = [2, 4]
        top.content[fi][fi + 1] = "T"
        top.newColorMap[fi][fi + 1] = [5, 0]
        top.newColorMap[4][fi] = [1, 6]          # espacio con fondo: opaco
    doc2 = from_durg(to_durg(doc))
    assert doc2.frameCount == 3 and len(doc2.layers) == 2
    for fi in range(3):
        a, b = doc.composite_frame(fi), doc2.composite_frame(fi)
        assert a.content == b.content
        assert a.newColorMap == b.newColorMap
