from PySide6.QtWidgets import QStatusBar, QLabel
from PySide6.QtCore    import Qt


class StatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_lbl  = QLabel(""); self._pos_lbl.setMinimumWidth(160)
        self._tool_lbl = QLabel(""); self._tool_lbl.setMinimumWidth(100)
        self._frame_lbl= QLabel(""); self._frame_lbl.setMinimumWidth(80)
        self._zoom_lbl = QLabel(""); self._zoom_lbl.setMinimumWidth(110)
        for lbl in (self._pos_lbl, self._tool_lbl, self._frame_lbl, self._zoom_lbl):
            self.addPermanentWidget(lbl)

    def set_pos(self, col, row, ch=None, fg=None, bg=None):
        if col is None:
            self._pos_lbl.setText("")
        else:
            char_info = f"  '{ch}' fg={fg} bg={bg}" if ch else ""
            self._pos_lbl.setText(f"Col {col}  Fil {row}{char_info}")

    def set_tool(self, name: str):
        self._tool_lbl.setText(name)

    def set_frame(self, cur: int, total: int):
        self._frame_lbl.setText(f"Frame {cur}/{total}")

    def set_zoom(self, pt: int, cw: int, rh: int):
        self._zoom_lbl.setText(f"{pt}pt  {cw}×{rh}px")
