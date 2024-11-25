from pathlib import Path
import os

class Config:
    # Application settings
    APP_NAME = "Sprout"
    VERSION = "1.0.0"
    STATE = "Carrot"  # Current working state marker
    
    # Model settings
    MODEL_ID = "facebook/musicgen-stereo-small"
    MAX_DURATION = 8  # seconds
    MIN_DURATION = 1  # seconds
    SAMPLE_RATE = 32000
    USE_FLOAT32 = True
    
    # Generation settings
    GUIDANCE_SCALE = 3.0
    AUDIO_CHANNELS = 2
    
    # Model constraints
    MAX_POSITION_EMBEDDINGS = 2048  # From model config
    VOCAB_SIZE = 2048  # From model config
    PAD_TOKEN_ID = 2048  # From model config
    BOS_TOKEN_ID = 2048  # From model config
    
    # UI settings
    WINDOW_WIDTH = 900
    WINDOW_HEIGHT = 700
    MAX_PROMPT_LENGTH = 500
    UI_SPACING = 12
    UI_MARGIN = 16
    
    # Theme colors (Forest theme)
    BACKGROUND_COLOR = "#3c6d4e"  # Dark forest green
    ACCENT_COLOR = "#85b79e"      # Light forest green
    TEXT_COLOR = "#FFFFFF"        # White
    SECONDARY_COLOR = "#2a4d37"   # Darker forest green
    WAVEFORM_COLOR = "#a8c9b5"    # Lighter green for waveform
    PLAYHEAD_COLOR = "#d4e7dc"    # Very light green for playhead
    
    # Waveform settings
    WAVEFORM_HEIGHT = 120
    WAVEFORM_PADDING = 16
    WAVEFORM_LINE_WIDTH = 1
    PLAYHEAD_WIDTH = 2
    
    # History settings
    HISTORY_HEIGHT = 150
    HISTORY_ITEM_HEIGHT = 60
    
    # Paths
    ROOT_DIR = Path(__file__).parent.parent
    CACHE_DIR = Path(os.getenv('APPDATA')) / APP_NAME if os.getenv('APPDATA') else Path.home() / '.cache' / APP_NAME
    SAMPLES_DIR = CACHE_DIR / "samples"
    
    # Audio settings
    EXPORT_FORMAT = "wav"
    FADE_MS = 20  # Fade duration in milliseconds
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        
    @classmethod
    def get_samples_per_token(cls) -> float:
        """Calculate approximate samples per token based on model constraints."""
        max_duration = 30  # Maximum duration the model is typically trained on
        return (max_duration * cls.SAMPLE_RATE) / cls.MAX_POSITION_EMBEDDINGS
        
    @classmethod
    def get_button_style(cls, primary=False) -> str:
        """Get styled button CSS."""
        return f"""
            QPushButton {{
                background-color: {cls.ACCENT_COLOR if primary else cls.SECONDARY_COLOR};
                color: {cls.TEXT_COLOR};
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: {'bold' if primary else 'normal'};
            }}
            QPushButton:hover {{
                background-color: {'#96c8af' if primary else '#3a5d47'};
            }}
            QPushButton:disabled {{
                background-color: #2a4d37;
                color: #5a7d67;
            }}
        """
    
    @classmethod
    def get_slider_style(cls) -> str:
        """Get styled slider CSS."""
        return f"""
            QSlider {{
                min-height: 24px;
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {cls.SECONDARY_COLOR};
                border-radius: 2px;
                margin: 0px;
            }}
            QSlider::handle:horizontal {{
                background: {cls.ACCENT_COLOR};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #96c8af;
            }}
            QSlider::sub-page:horizontal {{
                background: {cls.ACCENT_COLOR};
                border-radius: 2px;
            }}
        """
