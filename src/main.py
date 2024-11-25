import sys
import time
import shutil
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QThread, Signal, Slot, Qt
from .ui.main_window import MainWindow
from .audio.generator import AudioGenerator
from .config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeneratorThread(QThread):
    """Worker thread for audio generation to prevent UI freezing"""
    finished = Signal(object)  # Emits the generated audio data
    progress = Signal(int, str)  # Emits progress percentage and status message
    error = Signal(str)  # Emits error messages

    def __init__(self, generator, prompt, duration):
        super().__init__()
        self.generator = generator
        self.prompt = prompt
        self.duration = duration
        self._is_running = True

    def run(self):
        try:
            logger.info(f"Starting generation thread for prompt: '{self.prompt}'")
            
            # Update progress - Model preparation
            self.progress.emit(10, "Preparing model...")
            if not self._is_running:
                return
            
            # Generate audio
            self.progress.emit(30, "Generating audio...")
            if not self._is_running:
                return
                
            audio_data = self.generator.generate(self.prompt, self.duration)
            
            # Normalize audio
            self.progress.emit(80, "Processing audio...")
            if not self._is_running:
                return
                
            audio_data = self.generator.normalize_audio(audio_data)
            
            # Emit the result
            if self._is_running:
                self.progress.emit(100, "Generation complete!")
                self.finished.emit(audio_data)
            
        except Exception as e:
            logger.error(f"Error in generator thread: {str(e)}")
            self.error.emit(str(e))

    def stop(self):
        """Safely stop the thread"""
        logger.info("Stopping generator thread")
        self._is_running = False
        self.wait()

class Application(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        
        # Set application name and version
        self.setApplicationName(Config.APP_NAME)
        self.setApplicationVersion(Config.VERSION)
        
        logger.info(f"Initializing {Config.APP_NAME} v{Config.VERSION}")
        
        # Initialize components
        self.init_components()
        
        # Create and show main window
        self.main_window = MainWindow()
        self.setup_connections()
        self.main_window.show()
        
        logger.info("Application started successfully")

    def init_components(self):
        """Initialize application components"""
        # Ensure necessary directories exist
        Config.ensure_directories()
        logger.info(f"Using cache directory: {Config.CACHE_DIR}")
        logger.info(f"Using samples directory: {Config.SAMPLES_DIR}")
        
        # Initialize audio generator
        self.generator = AudioGenerator()
        
        # Initialize current audio data
        self.current_audio = None
        self.generator_thread = None
        self.current_audio_path = None

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Connect generate button
        self.main_window.generate_btn.clicked.connect(self.start_generation)

    def cleanup_thread(self):
        """Safely clean up the generator thread"""
        if self.generator_thread and self.generator_thread.isRunning():
            logger.info("Cleaning up generator thread")
            self.generator_thread.stop()
            self.generator_thread = None

    @Slot()
    def start_generation(self):
        """Start audio generation in a separate thread"""
        # Clean up any existing thread
        self.cleanup_thread()
        
        # Disable generate button and show progress
        self.main_window.generate_btn.setEnabled(False)
        self.main_window.generate_btn.setText("Generating...")
        self.main_window.show_progress(True, 0, "Starting generation...")
        
        # Get parameters from UI
        prompt = self.main_window.prompt_input.text()
        if not prompt:
            self.generation_error("Please enter a prompt")
            return
            
        duration = self.main_window.duration_slider.value() / 10.0
        
        logger.info(f"Starting generation with prompt: '{prompt}', duration: {duration}s")
        
        # Create and start generator thread
        self.generator_thread = GeneratorThread(self.generator, prompt, duration)
        self.generator_thread.finished.connect(self.generation_finished)
        self.generator_thread.progress.connect(self.update_progress)
        self.generator_thread.error.connect(self.generation_error)
        self.generator_thread.start()

    @Slot(int, str)
    def update_progress(self, percentage, status):
        """Update the progress bar and status label"""
        logger.info(f"Progress: {percentage}% - {status}")
        self.main_window.show_progress(True, percentage, status)

    @Slot(object)
    def generation_finished(self, audio_data):
        """Handle completed audio generation"""
        self.current_audio = audio_data
        
        # Save the generated audio to AppData
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        prompt_words = "-".join(self.main_window.prompt_input.text().split()[:3])
        filename = f"{prompt_words}-{timestamp}"
        
        try:
            self.current_audio_path = self.generator.save_audio(audio_data, filename)
            logger.info(f"Audio saved to: {self.current_audio_path}")
            
            # Update UI with the new audio data
            self.main_window.set_audio_data(audio_data, self.current_audio_path)
            self.main_window.show_progress(False)
            self.main_window.status_label.setText(
                "Audio generated successfully! Drag waveform to save elsewhere."
            )
            
        except Exception as e:
            logger.error(f"Error saving audio: {str(e)}")
            self.generation_error(f"Error saving audio: {str(e)}")
            return
        
        # Update UI
        self.main_window.generate_btn.setEnabled(True)
        self.main_window.generate_btn.setText("Generate")
        
        # Clean up thread
        self.cleanup_thread()

    @Slot(str)
    def generation_error(self, error_message):
        """Handle audio generation errors"""
        logger.error(f"Generation error: {error_message}")
        
        # Update UI
        self.main_window.generate_btn.setEnabled(True)
        self.main_window.generate_btn.setText("Generate")
        self.main_window.show_progress(False)
        
        # Show error in status
        self.main_window.status_label.setText(f"Error: {error_message}")
        
        # Clean up thread
        self.cleanup_thread()

def main():
    # Create and start application
    app = Application(sys.argv)
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
