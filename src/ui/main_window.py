from pathlib import Path
import numpy as np
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLineEdit, QSlider, QPushButton, QLabel, QFrame,
                              QFileDialog, QProgressBar)
from PySide6.QtCore import Qt, Slot, QMimeData
from PySide6.QtGui import QFont, QPalette, QColor, QDrag
from .waveform import WaveformWidget
from .history_panel import HistoryPanel
from ..config import Config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{Config.APP_NAME} - AI Audio Generator")
        self.setFixedSize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setup_ui()
        self.setup_styles()

    def setup_ui(self):
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(Config.UI_SPACING)
        layout.setContentsMargins(Config.UI_MARGIN, Config.UI_MARGIN, 
                                Config.UI_MARGIN, Config.UI_MARGIN)

        # Header section (Title + Prompt)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(Config.UI_SPACING // 2)
        
        # Title
        title = QLabel(Config.APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {Config.ACCENT_COLOR};
            margin-bottom: {Config.UI_SPACING // 2}px;
            font-family: 'Segoe UI', 'Inter', sans-serif;
        """)
        header_layout.addWidget(title)

        # Prompt input
        prompt_container = QWidget()
        prompt_layout = QVBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(4)
        
        prompt_label = QLabel("Enter your prompt:")
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Describe the audio you want to generate...")
        self.prompt_input.setMaxLength(Config.MAX_PROMPT_LENGTH)
        
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.prompt_input)
        header_layout.addWidget(prompt_container)
        
        layout.addLayout(header_layout)

        # Duration slider
        duration_container = QWidget()
        duration_layout = QHBoxLayout(duration_container)
        duration_layout.setContentsMargins(0, 0, 0, 0)
        duration_layout.setSpacing(Config.UI_SPACING)
        
        duration_label = QLabel("Duration:")
        duration_label.setFixedWidth(60)
        
        self.duration_slider = QSlider(Qt.Horizontal)
        self.duration_slider.setMinimum(Config.MIN_DURATION * 10)
        self.duration_slider.setMaximum(Config.MAX_DURATION * 10)
        self.duration_slider.setValue(40)  # Default 4 seconds
        self.duration_slider.setFixedHeight(24)  # Ensure enough height for handle
        
        self.duration_value = QLabel("4.0s")
        self.duration_value.setFixedWidth(40)
        self.duration_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.duration_slider.valueChanged.connect(self.update_duration_label)
        
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_slider)
        duration_layout.addWidget(self.duration_value)
        layout.addWidget(duration_container)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background: {Config.SECONDARY_COLOR};
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background: {Config.ACCENT_COLOR};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Waveform display
        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform)

        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(Config.UI_SPACING)
        
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setMinimumWidth(120)
        self.generate_btn.setStyleSheet(Config.get_button_style(primary=True))
        
        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.play_btn.setStyleSheet(Config.get_button_style())
        self.play_btn.clicked.connect(self.waveform.play_audio)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(Config.get_button_style())
        self.stop_btn.clicked.connect(self.waveform.stop_playback)
        
        controls_layout.addWidget(self.generate_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.stop_btn)
        layout.addLayout(controls_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {Config.ACCENT_COLOR};")
        layout.addWidget(self.status_label)

        # History panel (below controls)
        self.history_panel = HistoryPanel()
        self.history_panel.setFixedHeight(150)  # Shorter height
        layout.addWidget(self.history_panel)

        # Connect waveform signals
        self.waveform.playbackStarted.connect(self.on_playback_started)
        self.waveform.playbackStopped.connect(self.on_playback_stopped)

    def setup_styles(self):
        # Convert hex colors to QColor for proper manipulation
        secondary_color = QColor(Config.SECONDARY_COLOR)
        lighter_secondary = secondary_color.lighter(120)
        lighter_secondary_hex = f"#{lighter_secondary.red():02x}{lighter_secondary.green():02x}{lighter_secondary.blue():02x}"
        
        # Set the application style
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Config.BACKGROUND_COLOR};
            }}
            QWidget {{
                color: {Config.TEXT_COLOR};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QLineEdit {{
                padding: 8px 12px;
                background-color: {Config.SECONDARY_COLOR};
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                background-color: {lighter_secondary_hex};
            }}
            QLabel {{
                font-size: 13px;
            }}
            {Config.get_slider_style()}
        """)

    def show_progress(self, show: bool = True, progress: int = 0, status: str = ""):
        """Update the progress bar and status"""
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setValue(progress)
            self.status_label.setText(status)
        else:
            self.status_label.clear()

    def set_audio_data(self, audio_data: np.ndarray, file_path: Path = None):
        """Update the waveform with new audio data"""
        self.waveform.set_audio_data(audio_data, str(file_path) if file_path else None)
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Add to history if file was saved
        if file_path:
            self.history_panel.add_history_item(str(file_path))

    @Slot()
    def update_duration_label(self):
        value = self.duration_slider.value() / 10.0
        self.duration_value.setText(f"{value:.1f}s")

    @Slot()
    def on_playback_started(self):
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    @Slot()
    def on_playback_stopped(self):
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        """Handle application close event."""
        # Stop any playing audio
        if hasattr(self, 'waveform'):
            self.waveform.stop_playback()
        super().closeEvent(event)
