import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_bus import EventBus
from core.color_service import ColorService, PALETTE_256, ANSI_COLORS


def test_default_mode_16():
    bus = EventBus()
    svc = ColorService(bus)
    assert svc.mode == "16"
    assert svc.count() == 16


def test_default_colors():
    bus = EventBus()
    svc = ColorService(bus)
    assert svc.color(0) == "#000000"
    assert svc.color(15) == "#FFFFFF"


def test_16_mode_wraps():
    bus = EventBus()
    svc = ColorService(bus)
    assert svc.color(16) == svc.color(0)
    assert svc.color(17) == svc.color(1)


def test_256_mode():
    bus = EventBus()
    svc = ColorService(bus, mode="256")
    assert svc.mode == "256"
    assert svc.count() == 256
    # índice 17 = primer color del cubo con B>0: #00005F
    assert svc.color(17) != svc.color(0)


def test_set_mode_emits_event():
    bus = EventBus()
    svc = ColorService(bus)
    received = []
    bus.on("color_mode_changed", received.append)
    svc.set_mode("256")
    assert len(received) == 1
    assert received[0]["mode"] == "256"


def test_set_same_mode_no_event():
    bus = EventBus()
    svc = ColorService(bus)
    received = []
    bus.on("color_mode_changed", received.append)
    svc.set_mode("16")  # mismo modo — no debe emitir
    assert len(received) == 0


def test_palette_copy_is_independent():
    bus = EventBus()
    svc = ColorService(bus)
    p = svc.palette()
    p[0] = "#FF0000"
    assert svc.color(0) == "#000000"  # copia: el interno no cambia


def test_256_palette_length():
    assert len(PALETTE_256) == 256


def test_ansi_colors_are_first_16():
    assert ANSI_COLORS == PALETTE_256[:16]


def test_event_bus_subscribe_off():
    bus = EventBus()
    calls = []
    cb = lambda d: calls.append(d)
    bus.on("x", cb)
    bus.emit("x", 1)
    bus.off("x", cb)
    bus.emit("x", 2)
    assert calls == [1]
