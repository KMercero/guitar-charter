import os
import sys
import traceback
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QLineEdit, QProgressBar, QSpinBox, QFormLayout, QGroupBox
)
from PySide6.QtCore import QThread, Signal

from core.pipeline import chart_mp3


class Worker(QThread):
    progress = Signal(int, str)
    done = Signal(str)
    fail = Signal(str)

    def __init__(self, mp3, midi, out, name, artist, manual_bpm):
        super().__init__()
        self.mp3 = mp3
        self.midi = midi
        self.out = out
        self.name = name
        self.artist = artist
        self.manual_bpm = manual_bpm

    def run(self):
        try:
            out = chart_mp3(
                mp3_path=self.mp3 or None,
                gp_path=self.midi or None,
                out_dir=self.out,
                song_name=self.name,
                artist=self.artist,
                progress=lambda p, m: self.progress.emit(p, m),
                manual_bpm=self.manual_bpm,
            )
            self.done.emit(out)
        except Exception as e:
            traceback.print_exc()
            self.fail.emit(f"{type(e).__name__}: {e}")


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guitar Charter")
        self.resize(640, 620)
        lay = QVBoxLayout(self)

        self.mp3 = QLineEdit(placeholderText="MP3 path (audio — required for the game's song.ogg)…")
        b_mp3 = QPushButton("1. Choose MP3")
        b_mp3.clicked.connect(self.pick_mp3)
        lay.addWidget(self.mp3)
        lay.addWidget(b_mp3)

        self.midi = QLineEdit(placeholderText="MIDI path (.mid) — export from TuxGuitar: File > Export > MIDI…")
        b_midi = QPushButton("2. Choose MIDI file (.mid)")
        b_midi.clicked.connect(self.pick_midi)
        lay.addWidget(self.midi)
        lay.addWidget(b_midi)

        self.out = QLineEdit(placeholderText="Output folder…")
        b_out = QPushButton("3. Choose output folder")
        b_out.clicked.connect(self.pick_out)
        lay.addWidget(self.out)
        lay.addWidget(b_out)

        form = QGroupBox("Song info")
        f = QFormLayout(form)
        self.name = QLineEdit("Untitled")
        self.artist = QLineEdit("Unknown")
        f.addRow("Name", self.name)
        f.addRow("Artist", self.artist)
        lay.addWidget(form)

        cfg_box = QGroupBox("Options")
        cf = QFormLayout(cfg_box)
        self.bpm_override = QLineEdit()
        self.bpm_override.setPlaceholderText("Auto-detect (leave blank)")
        cf.addRow("BPM Override", self.bpm_override)
        lay.addWidget(cfg_box)

        self.run_btn = QPushButton("4. Chart Song")
        self.run_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        self.run_btn.clicked.connect(self.run)
        lay.addWidget(self.run_btn)

        self.bar = QProgressBar()
        lay.addWidget(self.bar)
        self.status = QLabel("Ready. Provide MP3 + MIDI (.mid) for perfect charts, or just MP3 for AI transcription.")
        lay.addWidget(self.status)

    def pick_mp3(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Choose MP3", "", "Audio (*.mp3 *.wav *.ogg)"
        )
        if p:
            self.mp3.setText(p)
            self.status.setText("MP3 selected.")

    def pick_midi(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Choose MIDI file", "", "MIDI (*.mid *.midi)"
        )
        if p:
            self.midi.setText(p)
            self.status.setText(f"{os.path.basename(p)} selected.")

    def pick_out(self):
        p = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if p:
            self.out.setText(p)
            self.status.setText("Output folder selected.")

    def run(self):
        if not self.out.text():
            self.status.setText("ERROR: Pick an output folder first.")
            return
        if not self.mp3.text() and not self.midi.text():
            self.status.setText("ERROR: Provide an MP3, a MIDI file, or both.")
            return

        manual_bpm = None
        bpm_text = self.bpm_override.text().strip()
        if bpm_text:
            try:
                manual_bpm = float(bpm_text)
            except ValueError:
                self.status.setText("ERROR: BPM Override must be a number.")
                return

        self.run_btn.setEnabled(False)

        self.worker = Worker(
            self.mp3.text(),
            self.midi.text(),
            self.out.text(),
            self.name.text(),
            self.artist.text(),
            manual_bpm,
        )
        self.worker.progress.connect(
            lambda p, m: (self.bar.setValue(p), self.status.setText(m))
        )
        self.worker.done.connect(self.finished)
        self.worker.fail.connect(self.failed)
        self.worker.start()

    def finished(self, out):
        self.bar.setValue(100)
        self.status.setText(f"Done → {out}")
        self.run_btn.setEnabled(True)

    def failed(self, error_msg):
        self.status.setText(f"CRASHED: {error_msg}")
        self.run_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Main()
    w.show()
    sys.exit(app.exec())