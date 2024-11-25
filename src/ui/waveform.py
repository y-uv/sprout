from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QTimer, QPointF, QMimeData, QUrl
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QLinearGradient, QDrag
import numpy as np
from ..config import Config
import sounddevice as sd
import logging

logger = logging.getLogger(__name__)

class WaveformWidget(QWidget):
    playbackStarted = Signal()
    playbackStopped = Signal()
    waveformDragged = Signal(str)  # Emits the target path when dragged
    seeked = Signal(float)  # Emits the seek position in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(Config.WAVEFORM_HEIGHT)
        self.setAcceptDrops(True)
        
        # Audio data
        self.audio_data = None
        self.audio_path = None
        self.sample_rate = Config.SAMPLE_RATE
        self.mono_data = None  # Store mono data for painting
        
        # Playback state
        self.is_playing = False
        self.is_looping = True  # Enable looping by default
        self.playhead_position = 0
        self.stream = None
        
        # Setup playback timer
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_playhead)
        self.playback_timer.setInterval(16)  # ~60 FPS
        
        # Visual settings
        self.waveform_color = QColor(Config.WAVEFORM_COLOR)
        self.playhead_color = QColor(Config.PLAYHEAD_COLOR)
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects
        
        # Initialize gradient
        self.gradient = QLinearGradient(0, 0, 0, Config.WAVEFORM_HEIGHT)
        self.gradient.setColorAt(0, self.waveform_color.lighter(120))
        self.gradient.setColorAt(1, self.waveform_color)
        
        # Cursor settings
        self.setCursor(Qt.PointingHandCursor)

    def set_audio_data(self, audio_data: np.ndarray, path: str = None):
        """Set the audio data to display and optionally its file path."""
        self.audio_data = audio_data
        self.audio_path = path
        self.playhead_position = 0
        
        # Compute mono data for visualization
        if audio_data is not None:
            self.mono_data = np.mean(audio_data, axis=0)
        else:
            self.mono_data = None
            
        self.stop_playback()
        self.update()
        logger.info(f"Set audio data with shape: {audio_data.shape}")

    def paintEvent(self, event):
        if self.audio_data is None or self.mono_data is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), QColor(Config.SECONDARY_COLOR))

        # Calculate waveform
        width = self.width() - 2 * Config.WAVEFORM_PADDING
        height = self.height() - 2 * Config.WAVEFORM_PADDING
        center_y = self.height() / 2

        if width > 0:
            # Resample data to match display width
            samples_per_pixel = len(self.mono_data) / width
            resampled_data = []
            
            for i in range(width):
                start = int(i * samples_per_pixel)
                end = int((i + 1) * samples_per_pixel)
                if start < len(self.mono_data):
                    chunk = self.mono_data[start:end]
                    if len(chunk) > 0:
                        resampled_data.append(np.max(np.abs(chunk)))
                    else:
                        resampled_data.append(0)
                else:
                    resampled_data.append(0)

            # Create waveform path
            path = QPainterPath()
            scale_factor = height / 2
            
            # Move to start position
            x = Config.WAVEFORM_PADDING
            y = center_y
            path.moveTo(x, y)

            # Draw top half
            for i, amplitude in enumerate(resampled_data):
                x = i + Config.WAVEFORM_PADDING
                y = center_y - (amplitude * scale_factor)
                path.lineTo(x, y)

            # Draw bottom half (mirror)
            for i in range(len(resampled_data) - 1, -1, -1):
                x = i + Config.WAVEFORM_PADDING
                y = center_y + (resampled_data[i] * scale_factor)
                path.lineTo(x, y)

            path.closeSubpath()

            # Draw filled waveform with gradient
            painter.fillPath(path, self.gradient)

            # Draw outline
            pen = QPen(self.waveform_color.darker(120))
            pen.setWidth(Config.WAVEFORM_LINE_WIDTH)
            painter.strokePath(path, pen)

            # Draw playhead if playing
            if self.is_playing or self.playhead_position > 0:
                playhead_x = (self.playhead_position * width / len(self.mono_data)) + Config.WAVEFORM_PADDING
                pen = QPen(self.playhead_color)
                pen.setWidth(Config.PLAYHEAD_WIDTH)
                painter.setPen(pen)
                painter.drawLine(int(playhead_x), Config.WAVEFORM_PADDING, 
                               int(playhead_x), self.height() - Config.WAVEFORM_PADDING)

    def mousePressEvent(self, event):
        if self.audio_data is None:
            return
            
        if event.button() == Qt.LeftButton:
            if event.modifiers() == Qt.ShiftModifier and self.audio_path:
                # Shift + Click = Drag file
                self.start_drag()
            else:
                # Normal click = Seek
                self.seek_to_position(event.x())
                if not self.is_playing:
                    self.play_audio()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.audio_data is not None:
            self.seek_to_position(event.x())
            if not self.is_playing:
                self.play_audio()

    def seek_to_position(self, x_pos):
        """Seek to position based on x coordinate."""
        if self.audio_data is None:
            return
            
        # Calculate position in samples
        width = self.width() - 2 * Config.WAVEFORM_PADDING
        x_relative = x_pos - Config.WAVEFORM_PADDING
        if x_relative < 0:
            x_relative = 0
        elif x_relative > width:
            x_relative = width
            
        position_ratio = x_relative / width
        new_position = int(position_ratio * len(self.mono_data))
        
        # Update playhead
        self.playhead_position = new_position
        self.update()
        
        # Emit seek signal
        seek_time = new_position / self.sample_rate
        self.seeked.emit(seek_time)
        logger.info(f"Seeked to position: {seek_time:.2f}s")

    def start_drag(self):
        """Start drag operation for the audio file."""
        if not self.audio_path:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set the file path as both text and URL
        mime_data.setText(self.audio_path)
        mime_data.setUrls([QUrl.fromLocalFile(self.audio_path)])
        
        drag.setMimeData(mime_data)
        
        # Start drag operation
        result = drag.exec_(Qt.CopyAction)
        if result == Qt.CopyAction:
            logger.info(f"File dragged: {self.audio_path}")
            self.waveformDragged.emit(self.audio_path)

    def play_audio(self):
        """Start audio playback."""
        if self.audio_data is not None:
            self.is_playing = True
            
            try:
                # Start audio playback using sounddevice
                self.stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=2,
                    callback=self.audio_callback
                )
                self.stream.start()
                self.playback_timer.start()
                self.playbackStarted.emit()
                logger.info("Started audio playback")
            except Exception as e:
                logger.error(f"Error starting playback: {str(e)}")
                self.stop_playback()

    def stop_playback(self):
        """Stop audio playback."""
        if self.is_playing:
            self.is_playing = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    logger.error(f"Error stopping stream: {str(e)}")
                self.stream = None
            self.playback_timer.stop()
            self.update()
            self.playbackStopped.emit()
            logger.info("Stopped audio playback")

    def audio_callback(self, outdata, frames, time, status):
        """Callback for audio playback."""
        if status:
            logger.warning(f"Audio callback status: {status}")
            
        if self.audio_data is not None:
            end_pos = min(self.playhead_position + frames, len(self.audio_data[0]))
            data = self.audio_data[:, self.playhead_position:end_pos]
            
            if data.shape[1] < frames:
                if self.is_looping:
                    # Calculate remaining frames needed
                    remaining_frames = frames - data.shape[1]
                    # Reset playhead to start
                    self.playhead_position = 0
                    # Get additional data from start
                    additional_data = self.audio_data[:, :remaining_frames]
                    # Combine data
                    outdata[:data.shape[1]] = data.T
                    outdata[data.shape[1]:] = additional_data.T
                    self.playhead_position = remaining_frames
                else:
                    outdata[:data.shape[1]] = data.T
                    outdata[data.shape[1]:] = 0
                    self.stop_playback()
            else:
                outdata[:] = data.T
                self.playhead_position += frames

    def update_playhead(self):
        """Update the playhead position and redraw."""
        self.update()
