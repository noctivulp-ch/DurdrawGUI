# durdraw_file.py — durdraw por Sam Foster — BSD 3-Clause License
# Ingested into DurdrawGUI; imports redirigidos a submódulo interno.
import datetime
import gzip
import json
import os
import pickle

from .durdraw_options import Options
from .durdraw_movie import Movie

old_16_pal_to_new = {
    0: 0,  1: 7,  2: 3,  3: 5,  4: 1,  5: 6,  6: 2,  7: 4,
    8: 0,  9: 15, 10: 11, 11: 13, 12: 9, 13: 14, 14: 10, 15: 12, 16: 16,
}

old_256_pal_to_new = {
    0: 0,  1: 7,  2: 3,  3: 5,  4: 1,  5: 6,  6: 2,  7: 4,
    8: 241, 9: 8, 10: 9, 11: 10, 12: 11, 13: 12, 14: 13, 15: 14, 16: 15,
}

colors_to_html = {
    0: '#000000', 1: '#000000', 2: '#0000AA', 3: '#00AA00', 4: '#00AAAA',
    5: '#AA0000', 6: '#AA00AA', 7: '#AA5500', 8: '#AAAAAA', 9: '#555555',
    10: '#5555FF', 11: '#55FF55', 12: '#55FFFF', 13: '#FF5555',
    14: '#FF55FF', 15: '#FFFF00', 16: '#FFFFFF',
}


def write_frame_to_html_file(mov, colorMode, frame, file_path, gzipped=False):
    opener = gzip.open if gzipped else open
    with opener(file_path, 'wt') as f:
        html = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<style>body{color:#FFF;background:#000}'
            '#o{font-size:12pt;font-family:"Courier New",monospace;line-height:13pt;color:#FFF}'
            '</style>\n</head>\n<body>\n<pre id="o">\n'
        )
        for posY in range(mov.sizeY):
            for posX in range(mov.sizeX):
                fgColor = frame.newColorMap[posY][posX][0]
                bgColor = frame.newColorMap[posY][posX][1]
                c = frame.content[posY][posX]
                try:
                    if colorMode == "16":
                        bgColor += 1
                        if bgColor == 9:
                            bgColor = 0
                    if colorMode == "256":
                        fgColor += 1
                        bgColor += 1
                    fg_h = colors_to_html.get(fgColor, '#AAAAAA')
                    bg_h = colors_to_html.get(bgColor, '#000000')
                    html += f'<span style="color:{fg_h};background-color:{bg_h};">{c}</span>'
                except Exception:
                    pass
            html += '\n'
        html += '        </pre>\n    </body>\n</html>\n'
        f.write(html)


def serialize_to_json_file(opts, colorMode, charEncoding, movie, file_path, gzipped=True):
    opener = gzip.open if gzipped else open
    with opener(file_path, 'wt') as f:
        header = {
            'formatVersion': opts.saveFileFormat,
            'colorFormat': colorMode,
            'preferredFont': 'fixed',
            'encoding': charEncoding,
            'name': '',
            'artist': '',
            'framerate': opts.framerate,
            'sizeX': movie.sizeX,
            'sizeY': movie.sizeY,
            'extra': None,
            'frames': None,
        }
        frames_data = []
        for fn, frame in enumerate(movie.frames):
            newColorMap = []
            for posX in range(movie.sizeX):
                newColorMap.append([])
                for posY in range(movie.sizeY):
                    try:
                        newColorMap[posX].append(frame.newColorMap[posY][posX])
                    except Exception:
                        newColorMap[posX].append([8, 0])
            newFrame = [''.join(line) for line in frame.content]
            frames_data.append({
                'frameNumber': fn + 1,
                'delay': frame.delay,
                'contents': newFrame,
                'colorMap': newColorMap,
            })
        header['frames'] = frames_data
        fullMovie = {'DurMovie': header}
        json_str = json.dumps(fullMovie, indent=2)
        f.write(_clean_up_json_output(json_str))


def _clean_up_json_output(json_str):
    s = json_str
    s = s.replace("[\n            [", "[[")
    s = s.replace("[\n              ", "[")
    s = s.replace(",\n             ", ",")
    s = s.replace("\n            ],", "],")
    s = s.replace("],\n            [", "],[")
    s = s.replace("\n            ]", "]")
    s = s.replace("\n          ],", "],")
    return s


def get_file_mod_date_time(filename):
    t = os.path.getmtime(filename)
    return str(datetime.datetime.fromtimestamp(t, tz=datetime.timezone.utc))[:19]


def get_dur_file_colorMode_and_charMode(f):
    f.seek(0)
    try:
        data = json.load(f)
    except Exception:
        return False
    colorMode = data['DurMovie']['colorFormat']
    try:
        charEncoding = data['DurMovie']['encoding']
    except Exception:
        charEncoding = 'utf-8'
    if charEncoding == 'Utf-8':
        charEncoding = 'utf-8'
    return colorMode, charEncoding


def open_json_dur_file(f, colorMode='16', charEncoding='utf-8'):
    """Carga un archivo .dur JSON. Retorna dict {'opts': opts, 'mov': mov} o False."""
    f.seek(0)
    try:
        data = json.load(f)
    except Exception:
        return False

    dm = data['DurMovie']
    width, height = dm['sizeX'], dm['sizeY']
    file_colorMode = dm['colorFormat']
    newOpts = Options(width=width, height=height)
    newOpts.framerate = dm['framerate']
    newOpts.saveFileFormat = dm['formatVersion']

    newMov = Movie(newOpts)
    currentFrame = 0
    for frame_data in dm['frames']:
        newMov.addEmptyFrame()
        newMov.nextFrame()
        for line_num, line in enumerate(frame_data['contents']):
            if line_num < len(newMov.frames[currentFrame].content):
                newMov.frames[currentFrame].content[line_num] = list(line)
        cmap = frame_data['colorMap']
        for x in range(width):
            for y in range(height):
                colorPair = list(cmap[x][y]) if x < len(cmap) and y < len(cmap[x]) else [8, 0]
                if colorMode == '16' and file_colorMode == '256':
                    if colorPair[0] > 16:
                        colorPair = [8, 0]
                newMov.frames[currentFrame].colorMap[y, x] = tuple(colorPair)
                newMov.frames[currentFrame].newColorMap[y][x] = colorPair
        newMov.frames[currentFrame].delay = frame_data.get('delay', 0)
        currentFrame += 1

    newMov.deleteCurrentFrame()
    newMov.gotoFrame(1)
    return {'opts': newOpts, 'mov': newMov}


def convert_old_color_to_new(oldPair, colorMode="16"):
    newFg, newBg = oldPair[0], oldPair[1]
    if colorMode == "16":
        if oldPair[0] in old_16_pal_to_new:
            newFg = old_16_pal_to_new[oldPair[0]] + 1
        if oldPair[1] in old_16_pal_to_new:
            newBg = old_16_pal_to_new[oldPair[1]]
    if colorMode == "256":
        if oldPair[0] in old_256_pal_to_new:
            newFg = old_256_pal_to_new[oldPair[0]] + 1
        newBg = oldPair[1]
    return [newFg, newBg]


class DurUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        module = "core.durdraw.durdraw_movie"
        return super().find_class(module, name)
