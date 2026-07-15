# durdraw_ansiparse.py — durdraw por Sam Foster — BSD 3-Clause License
# Ingested into DurdrawGUI; imports redirigidos, pdb eliminado.

import sys
import struct
from itertools import count

from . import durdraw_movie as durmovie
from . import durdraw_color as dur_ansilib
from . import durdraw_sauce as dursauce
from .plugins import convert_charset as durchar
from . import log

LOGGER = log.getLogger('ansiparse', level='DEBUG', override=True)


ansi_color_to_durcolor_table = {
    '30': 'Black', '31': 'Red',     '32': 'Green',   '33': 'Yellow',
    '34': 'Blue',  '35': 'Magenta', '36': 'Cyan',    '37': 'White',
    '40': 'Black', '41': 'Red',     '42': 'Green',   '43': 'Yellow',
    '44': 'Blue',  '45': 'Magenta', '46': 'Cyan',    '47': 'White',
}

color_name_to_durcolor_table = {
    'Black': 0, 'Red': 5, 'Green': 3, 'Yellow': 7,
    'Blue': 2, 'Magenta': 6, 'Cyan': 4, 'White': 8,
}


def ansi_color_to_durcolor(ansiColor):
    colorName = ansi_color_to_durcolor_table[ansiColor]
    return color_name_to_durcolor_table[colorName]


def find_next_alpha(text, i):
    for j in count(i):
        if text[j].isalpha():
            return j
    return None


def get_width_and_height_of_ansi_blob(text, width=80):
    i = 0
    col_num = 0
    line_num = 0
    max_col = 0
    saved_col_num = 0
    saved_line_num = 0
    while i < len(text):
        if i % 10_000 == 0 or i + 1 == len(text):
            LOGGER.debug('scanning', {'i': i + 1, 'total': len(text), 'pct': round((i + 1) / len(text) * 100, 2)})
        if text[i:i + 2] == '\x1B[':
            match = find_next_alpha(text, i + 1)
            if not match:
                i += 1
                continue
            end_index = match
            if text[end_index] == 'A':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                line_num -= move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'B':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                line_num += move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'C':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                col_num += move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'D':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                col_num -= move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'H':
                escape_sequence = text[i + 2:end_index]
                escape_codes = escape_sequence.split(';')
                if len(escape_codes) > 1:
                    if escape_codes[0].isnumeric():
                        line_num = int(escape_codes[0])
                    if escape_codes[1].isnumeric():
                        col_num = int(escape_codes[1])
                elif len(escape_codes) == 1:
                    if escape_codes[0].isnumeric():
                        col_num = int(escape_codes[0])
                i = end_index + 1
                continue
            elif text[end_index] == 'J':
                escape_sequence = text[i + 2:end_index]
                if not escape_sequence:
                    escape_sequence = '0'
                if escape_sequence == '2':
                    col_num, line_num = 0, 0
                i = end_index + 1
                continue
            elif text[end_index] == 's':
                saved_col_num = col_num
                saved_line_num = line_num
            elif text[end_index] == 'u':
                col_num = saved_col_num
                line_num = saved_line_num
            i = end_index + 1
            continue
        elif text[i] == '\n':
            line_num += 1
            if col_num > max_col:
                max_col = col_num
            col_num = 0
        elif text[i] == '\r':
            pass
        elif text[i:i + 5] == 'SAUCE' and len(text) - i == 128:
            i += 128
        else:
            if col_num == width:
                col_num = 0
                line_num += 1
            col_num += 1
        i += 1
    return max_col, line_num


def parse_ansi_escape_codes(text, filename=None, appState=None, caller=None,
                             console=False, debug=False,
                             convert_control_codes=True, maxWidth=80):
    sauce = None

    if isinstance(text, bytes):
        text = text.decode('cp437')
    if filename:
        sauce = dursauce.SauceParser()
        sauce.parse_file(filename)
        if sauce.sauce_found:
            if appState is not None:
                appState.sauce = sauce
            if sauce.width is None:
                sauce.width = maxWidth
            maxWidth = sauce.width
            width = sauce.width
            height = sauce.height

    if sauce is not None:
        if not sauce.height:
            width, height = get_width_and_height_of_ansi_blob(text)
            width = sauce.width
        if not sauce.sauce_found or width > 200 or height > 1200:
            width, height = get_width_and_height_of_ansi_blob(text)
    else:
        width, height = get_width_and_height_of_ansi_blob(text)

    width = max(width, maxWidth)
    height += 1
    height = max(height, 25)

    wrapWidth = getattr(appState, 'wrapWidth', 80) if appState else 80
    colorMode = getattr(appState, 'colorMode', '16') if appState else '16'
    default_fg_color = getattr(appState, 'defaultFgColor', 8) if appState else 8
    default_bg_color = getattr(appState, 'defaultBgColor', 0) if appState else 0
    app_debug = getattr(appState, 'debug', False) if appState else False

    if wrapWidth == 80 and width > 750:
        width = 80
    if height > 8500:
        height = 1000

    new_frame = durmovie.Frame(width, height + 1)
    i = 0
    col_num = 0
    line_num = 0
    max_col = 0
    fg_color = default_fg_color
    bg_color = default_bg_color
    bold = False
    saved_col_num = 0
    saved_line_num = 0
    parse_error = False

    while i < len(text):
        if i % 10_000 == 0 or i + 1 == len(text):
            LOGGER.debug('parsing', {'i': i + 1, 'total': len(text), 'pct': round((i + 1) / len(text) * 100, 2)})
        if text[i:i + 2] == '\x1B[':
            match = find_next_alpha(text, i + 1)
            if not match:
                i += 1
                continue
            end_index = match
            if text[end_index] == 'm':
                escape_sequence = text[i + 2:end_index]
                escape_codes = escape_sequence.split(';')
                codeList = []
                for code in escape_codes:
                    try:
                        codeList.append(int(code))
                    except Exception:
                        pass
                if len(codeList) > 1 and colorMode == "256":
                    bg_color = default_bg_color
                    if codeList[0] == 38 and codeList[1] == 5 and len(codeList) == 3:
                        fg_color = codeList.pop()
                        codeList = [fg_color]
                    elif codeList[0] == 48 and codeList[1] == 5 and len(codeList) == 3:
                        bg_color = codeList.pop()
                        codeList = [fg_color]
                for code in codeList:
                    if code == 0:
                        fg_color = default_fg_color
                        bg_color = default_bg_color
                        bold = False
                    if code == 1:
                        bold = True
                    if fg_color < 9:
                        if bold:
                            fg_color += 8
                    if 29 < code < 38:
                        if bold:
                            code += 60
                        fg_color = dur_ansilib.ansi_code_to_dur_16_color.get(str(code), default_fg_color)
                        if fg_color in (-1, 0):
                            fg_color = 9 if bold else 1
                        if fg_color < 9 and bold:
                            fg_color += 8
                    elif 39 < code < 48:
                        bg_color = dur_ansilib.ansi_code_to_dur_16_color.get(str(code), 0) - 1
                        if bg_color == -1:
                            bg_color = 0
                    if fg_color in (-1, 0):
                        fg_color = 9 if bold else 1
                try:
                    new_frame.newColorMap[line_num][col_num] = [fg_color, bg_color]
                except Exception:
                    pass
                i = end_index + 1
                continue
            elif text[end_index] == 'A':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                line_num -= move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'B':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                line_num += move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'C':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                if col_num >= maxWidth:
                    col_num = 0
                    line_num += 1
                col_num += move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'D':
                escape_sequence = text[i + 2:end_index]
                move_by_amount = int(escape_sequence) if escape_sequence else 1
                col_num -= move_by_amount
                i = end_index + 1
                continue
            elif text[end_index] == 'H':
                escape_sequence = text[i + 2:end_index]
                escape_codes = escape_sequence.split(';')
                if len(escape_codes) > 1:
                    if escape_codes[0].isnumeric():
                        line_num = int(escape_codes[0])
                    if escape_codes[1].isnumeric():
                        col_num = int(escape_codes[1])
                elif len(escape_codes) == 1:
                    if escape_codes[0].isnumeric():
                        col_num = int(escape_codes[0])
                i = end_index + 1
                continue
            elif text[end_index] == 'J':
                escape_sequence = text[i + 2:end_index]
                if not escape_sequence:
                    escape_sequence = '0'
                if escape_sequence == '2':
                    new_frame = durmovie.Frame(width, height + 1)
                    col_num, line_num = 0, 0
                i = end_index + 1
                continue
            elif text[end_index] == 's':
                i = end_index + 1
                continue
            elif text[end_index] == 'u':
                i = end_index + 1
                continue
            else:
                if app_debug and caller:
                    caller.notify(f"Unknown escape character type: {text[end_index]}")
                i = end_index + 1
                continue
        elif text[i] == '\n':
            line_num += 1
            if col_num > max_col:
                max_col = col_num
            col_num = 0
        elif text[i] == '\r':
            pass
        elif text[i] in ('\x00', '\x1a'):
            pass
        elif text[i:i + 5] == 'SAUCE' and len(text) - i == 128:
            i += 128
        else:
            if col_num >= maxWidth:
                col_num = 0
                line_num += 1
            character = text[i]
            try:
                if ord(character) < 0x19:
                    character = chr(durchar.cp437_control_codes_to_utf8[ord(character)])
                new_frame.content[line_num][col_num] = character
            except TypeError as e:
                if console:
                    print(f"Type error: {e}")
            except IndexError:
                parse_error = True
                if debug and caller:
                    caller.notify(f"Error writing content at line {line_num}, col {col_num}")
            try:
                new_frame.newColorMap[line_num][col_num] = [fg_color, bg_color]
            except IndexError:
                parse_error = True
                if debug and caller:
                    caller.notify(f"Error writing color at line {line_num}, col {col_num}")
            col_num += 1
        i += 1

    if console:
        print(f"\nLines: {line_num}, Columns: {max_col}")
    if parse_error and app_debug and caller:
        caller.notify("Possible errors detected while loading this file.")

    height = line_num
    width = max_col
    frame = durmovie.Frame(height, width)
    return new_frame
