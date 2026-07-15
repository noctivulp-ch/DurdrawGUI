# durdraw_movie.py — durdraw por Sam Foster — BSD 3-Clause License
# Ingested into DurdrawGUI; imports redirigidos a submódulo interno.
from copy import deepcopy
from .durdraw_options import Options
from . import log
import json
import re


def init_list_colorMap(width, height):
    colorMap = []
    dummyColor = [8, 0]
    for h in range(height):
        colorMap.append([])
        for w in range(width):
            colorMap[h].append(list(dummyColor))
    return colorMap


def convert_dict_colorMap(oldMap, width, height):
    newMap = init_list_colorMap(width, height)
    for x in range(height):
        for y in range(width):
            newMap[x][y] = list(oldMap[(x, y)])
    return newMap


def convert_movie_16_to_256_color_palette(mov):
    pass  # placeholder; conversión real en change_palette_16_to_256()


class Frame():
    """Frame class — single canvas frame of animation."""

    def __init__(self, width, height):
        self.content = []
        self.colorMap = {}
        self.newColorMap = init_list_colorMap(width, height)
        self.sizeX = width
        self.width = width
        self.sizeY = height
        self.height = height
        self.delay = 0

        for x in range(height):
            self.content.append([])
            for y in range(width):
                self.content[x].append(' ')

        self.initOldColorMap()
        self.setDelayValue(0)

        self.log = log.getLogger('frame')
        self.log.info('frame initialized', {'width': width, 'height': height})

    def flip_horizontal(self):
        self.content = self.content[::-1]
        self.newColorMap.reverse()

    def flip_vertical(self):
        for x in range(self.height):
            self.content[x] = self.content[x][::-1]
            self.newColorMap[x].reverse()

    def setWidth(self, width):
        self.sizeX = width
        self.width = width

    def setHeight(self, height):
        self.sizeY = height
        self.height = height

    def setDelayValue(self, delayValue):
        self.delay = delayValue

    def initOldColorMap(self):
        self.colorMap = {}
        for x in range(self.sizeY):
            for y in range(self.sizeX):
                self.colorMap.update({(x, y): (1, 0)})

    def initColorMap(self, fg=7, bg=0):
        return [[[fg, 0] * self.sizeY] * self.sizeX]


class Movie():
    """Contains an array of Frames; options to add, remove, copy them."""

    def __init__(self, opts):
        self.frameCount = 0
        self.currentFrameNumber = 0
        self.sizeX = opts.sizeX
        self.sizeY = opts.sizeY
        self.opts = opts
        self.frames = []
        self.layers = {}
        self.addEmptyFrame()
        self.currentFrameNumber = self.frameCount
        self.currentFrame = self.frames[self.currentFrameNumber - 1]

        self.log = log.getLogger('movie')
        self.log.info('movie initialized', {'sizeX': self.sizeX, 'sizeY': self.sizeY})

    def addFrame(self, frame):
        self.frames.append(frame)
        self.frameCount += 1
        return True

    def addEmptyFrame(self):
        newFrame = Frame(self.sizeX, self.sizeY)
        self.frames.append(newFrame)
        self.frameCount += 1
        return True

    def insertCloneFrame(self):
        newFrame = Frame(self.sizeX, self.sizeY)
        self.frames.insert(self.currentFrameNumber, newFrame)
        newFrame.content = deepcopy(self.currentFrame.content)
        newFrame.colorMap = deepcopy(self.currentFrame.colorMap)
        newFrame.newColorMap = deepcopy(self.currentFrame.newColorMap)
        self.frameCount += 1
        return True

    # Alias usado por DurdrawGUI
    def duplicateCurrentFrame(self):
        return self.insertCloneFrame()

    def deleteCurrentFrame(self):
        if self.frameCount == 1:
            del self.frames[self.currentFrameNumber - 1]
            newFrame = Frame(self.sizeX, self.sizeY)
            self.frames.append(newFrame)
            self.currentFrame = self.frames[self.currentFrameNumber - 1]
        else:
            del self.frames[self.currentFrameNumber - 1]
            self.frameCount -= 1
            if self.currentFrameNumber != 1:
                self.currentFrameNumber -= 1
            self.currentFrame = self.frames[self.currentFrameNumber - 1]
        return True

    # Alias usado por DurdrawGUI
    def deleteFrame(self):
        return self.deleteCurrentFrame()

    def moveFramePosition(self, startPosition, newPosition):
        fromIndex = startPosition - 1
        toIndex = newPosition - 1
        self.frames.insert(toIndex, self.frames.pop(fromIndex))

    def gotoFrame(self, frameNumber):
        if 0 < frameNumber <= self.frameCount:
            self.currentFrameNumber = frameNumber
            self.currentFrame = self.frames[self.currentFrameNumber - 1]
            return True
        return False

    def nextFrame(self):
        if self.currentFrameNumber == self.frameCount:
            self.currentFrameNumber = 1
        else:
            self.currentFrameNumber += 1
        self.currentFrame = self.frames[self.currentFrameNumber - 1]

    def prevFrame(self):
        if self.currentFrameNumber == 1:
            self.currentFrameNumber = self.frameCount
        else:
            self.currentFrameNumber -= 1
        self.currentFrame = self.frames[self.currentFrameNumber - 1]

    def hasMultipleFrames(self):
        return len(self.frames) > 1

    def growCanvasWidth(self, growth):
        self.sizeX += growth
        self.opts.sizeX += growth

    def shrinkCanvasWidth(self, shrinkage):
        self.sizeY -= shrinkage
        self.opts.sizeY -= shrinkage

    def search_and_replace_color_pair(self, old_color, new_color, frange=None):
        if frange is not None:
            for frameNum in range(frange[0] - 1, frange[1]):
                frame = self.frames[frameNum]
                line_num = col_num = 0
                for line in frame.newColorMap:
                    for pair in line:
                        if pair == old_color:
                            try:
                                frame.newColorMap[line_num][col_num] = new_color
                            except Exception:
                                pass
                        col_num += 1
                    line_num += 1
                    col_num = 0
        else:
            frame = self.currentFrame
            line_num = col_num = 0
            for line in frame.newColorMap:
                for pair in line:
                    if pair == old_color:
                        try:
                            frame.newColorMap[line_num][col_num] = new_color
                        except Exception:
                            pass
                    col_num += 1
                line_num += 1
                col_num = 0

    def search_and_replace_color(self, old_color: int, new_color: int):
        for frame in self.frames:
            line_num = 0
            for line in frame.newColorMap:
                for pair in line:
                    if pair[0] == old_color:
                        frame.newColorMap[line_num][0] = new_color
                    if pair[1] == old_color:
                        frame.newColorMap[line_num][1] = new_color
                line_num += 1

    def search_and_replace(self, caller, search_str: str, replace_str: str):
        found = False
        for frame in self.frames:
            line_num = 0
            for line in frame.content:
                line_str = ''.join(line)
                if search_str in line_str:
                    match = re.search(f"{search_str}\\s*", line_str)
                    if match:
                        width = match.end() - match.start()
                        replace_with = replace_str[:width].ljust(width)
                        line_str = line_str[:match.start()] + replace_with + line_str[match.end():]
                    else:
                        if len(search_str) < len(replace_str):
                            line_str = line_str.replace(search_str, replace_str)
                        else:
                            line_str = line_str.replace(search_str, replace_str.ljust(len(search_str)))
                    frame.content[line_num] = list(line_str)
                    found = True
                line_num += 1
        return found

    def search_for_string(self, search_str: str, caller=None):
        for frame_num, frame in enumerate(self.frames):
            for line_num, line in enumerate(frame.content):
                line_str = ''.join(line)
                if search_str in line_str:
                    col = line_str.index(search_str) + 1
                    return {"line": line_num, "col": col, "frame": frame_num + 1}
        return False

    def change_palette_16_to_256(self):
        map16 = {1:16, 16:15, 15:14, 14:13, 13:12, 12:11, 11:10, 10:9,
                 9:8, 8:7, 7:6, 6:5, 5:4, 4:3, 3:2, 2:1}
        for frame in self.frames:
            for line in frame.newColorMap:
                for pair in line:
                    pair[0] = map16.get(pair[0], pair[0])

    def change_palette_256_to_16(self):
        map256 = {16:1, 15:16, 14:15, 13:14, 12:13, 11:12, 10:11, 9:10,
                  8:9, 7:8, 6:7, 5:6, 4:5, 3:4, 2:3, 1:2}
        for frame in self.frames:
            for line in frame.newColorMap:
                for pair in line:
                    pair[0] = map256.get(pair[0], pair[0])

    def contains_high_colors(self):
        for frame in self.frames:
            for line in frame.newColorMap:
                for pair in line:
                    if pair[0] > 16:
                        return True
        return False

    def contains_background_colors(self):
        for frame in self.frames:
            for line in frame.newColorMap:
                for pair in line:
                    if pair[1] > 0:
                        return True
        return False

    def strip_backgrounds(self):
        for frame in self.frames:
            for line in frame.newColorMap:
                for pair in line:
                    pair[1] = 0
        return True

    def strip_unprintable_characters(self):
        for frame in self.frames:
            for line_num, line in enumerate(frame.content):
                for col_num, char in enumerate(line):
                    if not char.isprintable():
                        frame.content[line_num][col_num] = ' '
        return True

    def shift_right(self):
        self.frames.insert(0, self.frames.pop())
        return True

    def shift_left(self):
        self.frames.append(self.frames.pop(0))
        return True

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)
