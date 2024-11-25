from PySide6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QLabel, 
                              QPushButton, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt, Signal
from .waveform import WaveformWidget
from ..config import Config
import numpy as np
import soundfile as sf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HistoryWaveform(WaveformWidget):
    """A modified waveform widget for history items that doesn't loop."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_looping = False  # Override to disable looping
        self.setFixedHeight(40)  # Smaller height for history items
        self.line_width = 7  # Thicker lines for history waveforms

class HistoryItem(QFrame):
    deleted = Signal(str)  # Emits path when deleted

    def __init__(self, audio_path: str, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.setup_ui()
        self.load_audio()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Left side: Name and delete button
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # File name label
        name_label = QLabel(Path(self.audio_path).stem)
        name_label.setStyleSheet(f"""
            color: {Config.TEXT_COLOR};
            font-size: 11px;
        """)
        info_layout.addWidget(name_label)
        
        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedWidth(60)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SECONDARY_COLOR};
                color: {Config.TEXT_COLOR};
                border: none;
                padding: 4px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        delete_btn.clicked.connect(self.delete_item)
        info_layout.addWidget(delete_btn)
        
        layout.addLayout(info_layout)

        # Right side: Mini waveform
        self.waveform = HistoryWaveform()
        layout.addWidget(self.waveform, stretch=1)

        # Style
        self.setStyleSheet(f"""
            HistoryItem {{
                background-color: {Config.SECONDARY_COLOR};
                border: 1px solid {Config.ACCENT_COLOR};
            }}
        """)

    def load_audio(self):
        try:
            audio_data, _ = sf.read(self.audio_path)
            if len(audio_data.shape) == 1:
                # Convert mono to stereo
                audio_data = np.stack([audio_data, audio_data])
            elif len(audio_data.shape) == 2:
                # Transpose if needed
                if audio_data.shape[0] > 2:
                    audio_data = audio_data.T
            self.waveform.set_audio_data(audio_data, self.audio_path)
        except Exception as e:
            logger.error(f"Error loading audio file {self.audio_path}: {str(e)}")

    def delete_item(self):
        try:
            # Stop playback if playing
            self.waveform.stop_playback()
            # Delete the file
            Path(self.audio_path).unlink()
            self.deleted.emit(self.audio_path)
            self.deleteLater()
            logger.info(f"Deleted audio file: {self.audio_path}")
        except Exception as e:
            logger.error(f"Error deleting file {self.audio_path}: {str(e)}")

class HistoryPanel(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_history()

    def setup_ui(self):
        # Create widget to hold the scroll content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setSpacing(0)  # No spacing between items
        self.content_layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins

        # Setup scroll area
        self.setWidget(self.content_widget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Style
        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Config.BACKGROUND_COLOR};
            }}
        """)
        
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Config.BACKGROUND_COLOR};
                border: 1px solid {Config.SECONDARY_COLOR};
                margin: 0px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {Config.SECONDARY_COLOR};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {Config.ACCENT_COLOR};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)

    def load_history(self):
        """Load existing audio files from the samples directory."""
        try:
            samples_dir = Config.SAMPLES_DIR
            if not samples_dir.exists():
                return

            # Load files in reverse chronological order
            audio_files = sorted(
                samples_dir.glob(f"*.{Config.EXPORT_FORMAT}"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            for audio_file in audio_files:
                self.add_history_item(str(audio_file))

        except Exception as e:
            logger.error(f"Error loading history: {str(e)}")

    def add_history_item(self, audio_path: str):
        """Add a new item to the history."""
        try:
            item = HistoryItem(audio_path)
            item.deleted.connect(self.on_item_deleted)
            self.content_layout.addWidget(item)
        except Exception as e:
            logger.error(f"Error adding history item: {str(e)}")

    def on_item_deleted(self, path: str):
        """Handle item deletion."""
        # The item widget will remove itself
        logger.info(f"History item deleted: {path}")
