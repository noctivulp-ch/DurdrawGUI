# durdraw_color.py — extraído de durdraw_color_curses.py por DurdrawGUI
# Sin dependencia de curses. Paleta de datos pura + helpers de secuencias ANSI.
# durdraw — BSD 3-Clause License — Sam Foster
from functools import lru_cache

# ── Tablas de conversión de paleta ────────────────────────────────────────────

legacy_256_to_256 = {
    1: 7, 2: 3, 3: 5, 4: 1, 5: 6, 6: 2, 7: 4, 8: 16,
    9: 12, 10: 10, 11: 14, 12: 9, 13: 13, 14: 11, 15: 15, 16: 8,
}

legacy_16_to_256 = {
    1: 7, 2: 3, 3: 5, 4: 1, 5: 6, 6: 2, 7: 4, 8: 16,
    9: 15, 10: 11, 11: 13, 12: 9, 13: 14, 14: 10, 15: 12, 16: 8,
}

legacy_16_to_16 = {
    1: 8, 2: 4, 3: 6, 4: 2, 5: 7, 6: 3, 7: 5, 8: 1,
    9: 16, 10: 12, 11: 14, 12: 10, 13: 15, 14: 11, 15: 13, 16: 9,
    'bg': {1: 7, 2: 3, 3: 5, 4: 1, 5: 6, 6: 2, 7: 4, 8: 8},
}

color_256_to_ansi_16 = {
    1: 4, 2: 2, 3: 6, 4: 1, 5: 5, 6: 3, 7: 7, 8: 8,
    9: 12, 10: 10, 11: 14, 12: 9, 13: 13, 14: 11, 15: 15, 16: 16,
}

mirc_16_to_color_16 = {
    0: 0, 1: 1, 2: 2, 3: 3, 10: 4, 5: 5, 6: 6, 7: 7,
    15: 8, 14: 9, 12: 10, 9: 11, 11: 12, 4: 13, 13: 14, 8: 15,
}

color_16_to_mirc_16 = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 10, 5: 5, 6: 6, 7: 7,
    8: 15, 9: 14, 10: 12, 11: 9, 12: 11, 13: 4, 14: 13, 15: 8, 16: 0,
}

color_256_to_mirc_16 = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 10, 5: 5, 6: 6, 7: 7,
    8: 15, 9: 14, 10: 12, 11: 9, 12: 11, 13: 4, 14: 13, 15: 8, 16: 0,
}

# Usado por durdraw_ansiparse para convertir secuencias ANSI → índice de color durdraw
ansi_code_to_dur_16_color = {
    '30': 0,  '31': 5,  '32': 3,  '33': 7,
    '34': 2,  '35': 6,  '36': 4,  '37': 8,
    '90': 9,  '91': 13, '92': 11, '93': 15,
    '94': 10, '95': 14, '96': 12, '97': 16,
    '40': 0,  '41': 5,  '42': 3,  '43': 7,
    '44': 2,  '45': 6,  '46': 4,  '47': 8,
}

# ── Paleta xterm-256 en hex (para renderizado GUI) ────────────────────────────
# Los primeros 16 siguen el orden de durdraw (1-based, 1=negro … 16=blanco brillante)
# Índices 17-256 son el cubo 6x6x6 y la escala de grises estándar de xterm.

def _build_xterm256_hex():
    """Genera los 256 colores xterm como cadenas hex '#RRGGBB'."""
    # Colores base de durdraw 1-16 (basados en VGA/CGA)
    base16 = [
        "#000000",  # 0  (negro, nunca usado como índice pero útil como fallback)
        "#000000",  # 1  negro
        "#0000AA",  # 2  azul
        "#00AA00",  # 3  verde
        "#00AAAA",  # 4  cian
        "#AA0000",  # 5  rojo
        "#AA00AA",  # 6  magenta
        "#AA5500",  # 7  marrón/amarillo oscuro
        "#AAAAAA",  # 8  gris claro
        "#555555",  # 9  gris oscuro (negro brillante)
        "#5555FF",  # 10 azul brillante
        "#55FF55",  # 11 verde brillante
        "#55FFFF",  # 12 cian brillante
        "#FF5555",  # 13 rojo brillante
        "#FF55FF",  # 14 magenta brillante
        "#FFFF55",  # 15 amarillo brillante
        "#FFFFFF",  # 16 blanco brillante
    ]
    # Cubo 6x6x6 (índices 17-232 en durdraw, pero estándar xterm es 16-231)
    levels = [0, 95, 135, 175, 215, 255]
    cube = []
    for r in levels:
        for g in levels:
            for b in levels:
                cube.append(f"#{r:02X}{g:02X}{b:02X}")
    # Escala de grises xterm (232-255)
    grays = [f"#{v:02X}{v:02X}{v:02X}" for v in range(8, 248, 10)]
    # Tabla completa: índice 0-255 (0 = unused/black, 1-16 = durdraw base, 17+ = xterm)
    table = base16 + cube + grays
    return table

XTERM256_HEX = _build_xterm256_hex()


# ── Helpers de secuencias de escape ANSI (sin curses) ────────────────────────

# Mapa fg durdraw-16 → código ANSI
ESCAPE_FG_MAP = {
    0: "0;30", 1: "0;30", 2: "0;34", 3: "0;32", 4: "0;36",
    5: "0;31", 6: "0;35", 7: "0;33", 8: "0;37",
    9: "1;30", 10: "1;34", 11: "1;32", 12: "1;36",
    13: "1;31", 14: "1;35", 15: "1;33", 16: "1;37",
}

# Mapa bg durdraw-16 → código ANSI
ESCAPE_BG_MAP = {
    0: "40", 1: "44", 2: "42", 3: "46", 4: "41",
    5: "45", 6: "43", 7: "47", 8: "40",
}


@lru_cache(maxsize=4096)
def get_color_code_16(fg: int, bg: int) -> str:
    """Secuencia ANSI para par de colores durdraw-16."""
    f = ESCAPE_FG_MAP.get(fg, "0;37")
    b = ESCAPE_BG_MAP.get(bg, "40")
    return f"\x1b[{f};{b}m"


@lru_cache(maxsize=4096)
def get_color_code_256(fg: int, bg: int) -> str:
    """Secuencia ANSI de 256 colores para par fg/bg (índices xterm 0-255)."""
    if 1 <= fg <= 16:
        fg_seq = f"\x1b[{ESCAPE_FG_MAP.get(fg, '0;37')}m"
    else:
        fg_seq = f"\x1b[38;5;{fg}m"
    if 0 <= bg <= 7:
        bg_seq = f"\x1b[{ESCAPE_BG_MAP.get(bg, '40')}m"
    else:
        bg_seq = f"\x1b[48;5;{bg}m"
    return fg_seq + bg_seq
