from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSlider
from PySide6.QtCore    import Qt, QTimer


class Timeline(QWidget):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent)
        self.app = app
        self.setFixedHeight(36)
        self._playing  = False
        self._timer    = QTimer(self)
        self._timer.timeout.connect(self._tick)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(28, 24)
        self._play_btn.setCheckable(True)
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)

        for icon, tip, slot in (
            ("|◀", "Primer frame",  lambda: app.goto_first_frame()),
            ("◀",  "Frame anterior",lambda: app.prev_frame()),
            ("▶",  "Frame siguiente",lambda: app.next_frame()),
            ("▶|", "Último frame",  lambda: app.goto_last_frame()),
        ):
            b = QPushButton(icon); b.setFixedSize(28, 24)
            b.setToolTip(tip); b.clicked.connect(slot)
            layout.addWidget(b)

        self._lbl = QLabel("Frame 1/1")
        layout.addWidget(self._lbl)

        self._fps_lbl = QLabel("FPS:")
        self._fps_slider = QSlider(Qt.Orientation.Horizontal)
        self._fps_slider.setRange(1, 30)
        self._fps_slider.setValue(8)
        self._fps_slider.setFixedWidth(80)
        self._fps_slider.valueChanged.connect(self._update_fps_label)
        self._fps_val_lbl = QLabel("8")
        layout.addWidget(self._fps_lbl)
        layout.addWidget(self._fps_slider)
        layout.addWidget(self._fps_val_lbl)
        layout.addStretch()

    def update_display(self, cur: int, total: int):
        self._lbl.setText(f"Frame {cur}/{total}")

    def stop_play(self):
        self._playing = False
        self._timer.stop()
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶")

    def _toggle_play(self):
        self._playing = not self._playing
        if self._playing:
            fps = self._fps_slider.value()
            self._timer.start(1000 // fps)
            self._play_btn.setText("⏸")
        else:
            self._timer.stop()
            self._play_btn.setText("▶")
        self._play_btn.setChecked(self._playing)

    def _tick(self):
        self.app.next_frame(wrap=True)

    def _update_fps_label(self, val: int):
        self._fps_val_lbl.setText(str(val))
        if self._playing:
            self._timer.start(1000 // val)
