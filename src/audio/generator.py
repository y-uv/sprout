import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import numpy as np
import soundfile as sf
from pathlib import Path
import logging
from ..config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioGenerator:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Load model and processor
        logger.info("Loading MusicGen stereo model...")
        try:
            self.processor = AutoProcessor.from_pretrained(Config.MODEL_ID)
            logger.info("Processor loaded successfully")
            
            self.model = MusicgenForConditionalGeneration.from_pretrained(
                Config.MODEL_ID,
                attn_implementation="eager"  # Prevents empty attention mask warning
            )
            logger.info("Model loaded successfully")
            
            self.model.to(self.device)
            logger.info(f"Model moved to {self.device}")
            
            # Set model to inference mode
            self.model.eval()
            
            if Config.USE_FLOAT32:
                self.model.to(torch.float32)
                logger.info("Model converted to float32")
            
            # Store model config values
            self.max_length = min(
                Config.MAX_POSITION_EMBEDDINGS,
                int(Config.MAX_DURATION * Config.SAMPLE_RATE / Config.get_samples_per_token())
            )
            logger.info(f"Using max length: {self.max_length} tokens")
            
            logger.info("Model initialization complete")
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

    def generate(self, prompt: str, duration: float, seed: int = None) -> np.ndarray:
        """
        Generate stereo audio from text prompt.
        
        Args:
            prompt: Text description
            duration: Length in seconds
            seed: Random seed (optional)
            
        Returns:
            Stereo audio array
        """
        logger.info(f"Starting generation with prompt: '{prompt}', duration: {duration}s")
        
        if seed is not None:
            torch.manual_seed(seed)
            logger.info(f"Set random seed: {seed}")
            
        try:
            # Process the input prompt
            logger.info("Processing input prompt...")
            inputs = self.processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to(self.device)
            logger.info("Prompt processed successfully")
            
            # Calculate tokens needed for the requested duration
            tokens_needed = int(duration * Config.SAMPLE_RATE / Config.get_samples_per_token())
            tokens_to_generate = min(tokens_needed, self.max_length)
            logger.info(f"Tokens needed: {tokens_needed}, generating: {tokens_to_generate}")
            
            # Generate audio
            logger.info("Starting audio generation...")
            with torch.no_grad():
                try:
                    # Generate the audio
                    audio_values = self.model.generate(
                        **inputs,
                        do_sample=True,
                        guidance_scale=Config.GUIDANCE_SCALE,
                        max_new_tokens=tokens_to_generate,
                        pad_token_id=Config.PAD_TOKEN_ID,
                        bos_token_id=Config.BOS_TOKEN_ID
                    )
                    logger.info("Raw generation complete")
                    logger.info(f"Generated tensor shape: {audio_values.shape}")
                    
                    # Get the waveform from the model's output
                    try:
                        # Try using the model's built-in conversion if available
                        waveform = self.model.generate_audio(audio_values)
                        audio_data = waveform.cpu().numpy()
                        logger.info("Used model's audio conversion")
                    except AttributeError:
                        # Fall back to raw output if generate_audio is not available
                        audio_data = audio_values.cpu().numpy()
                        logger.info("Used raw output conversion")
                    
                    logger.info(f"Converted to numpy array: {audio_data.shape}")
                    
                    # Remove batch dimension if present
                    if len(audio_data.shape) == 3:
                        audio_data = audio_data.squeeze(0)
                        logger.info(f"Removed batch dimension: {audio_data.shape}")
                    
                    # Ensure stereo output
                    if len(audio_data.shape) == 1:
                        # Convert mono to stereo
                        logger.info("Converting mono to stereo")
                        audio_data = np.stack([audio_data, audio_data])
                    elif audio_data.shape[0] > 2:
                        # Transpose if needed
                        logger.info("Transposing audio data")
                        audio_data = audio_data.T
                        if audio_data.shape[0] > 2:
                            # Take first two channels if more than stereo
                            logger.info("Taking first two channels")
                            audio_data = audio_data[:2]
                    
                    # Ensure exactly 2 channels
                    if audio_data.shape[0] != 2:
                        logger.warning(f"Unexpected channel count: {audio_data.shape[0]}, converting to stereo")
                        if len(audio_data.shape) == 1:
                            audio_data = np.stack([audio_data, audio_data])
                        else:
                            audio_data = np.stack([audio_data[0], audio_data[0]])
                    
                    # Calculate target duration in samples
                    target_samples = int(duration * Config.SAMPLE_RATE)
                    current_samples = audio_data.shape[1]
                    logger.info(f"Target samples: {target_samples}, Current samples: {current_samples}")
                    
                    if current_samples > target_samples:
                        logger.info(f"Trimming audio from {current_samples} to {target_samples} samples")
                        audio_data = audio_data[:, :target_samples]
                    elif current_samples < target_samples:
                        logger.info(f"Padding audio from {current_samples} to {target_samples} samples")
                        padding = np.zeros((2, target_samples - current_samples))
                        audio_data = np.concatenate([audio_data, padding], axis=1)
                    
                    logger.info(f"Final audio shape: {audio_data.shape}")
                    return audio_data
                    
                except Exception as e:
                    logger.error(f"Generation error: {str(e)}")
                    raise
            
        except Exception as e:
            logger.error(f"Error during generation: {str(e)}")
            raise

    def save_audio(self, audio_data: np.ndarray, filename: str) -> Path:
        """
        Save audio data to file.
        
        Args:
            audio_data: Stereo audio array (2 x samples)
            filename: Output filename (without extension)
            
        Returns:
            Path to saved file
        """
        try:
            # Ensure samples directory exists
            Config.ensure_directories()
            
            # Create full path
            output_path = Config.SAMPLES_DIR / f"{filename}.{Config.EXPORT_FORMAT}"
            logger.info(f"Saving audio to: {output_path}")
            
            # Normalize audio before saving
            audio_data = self.normalize_audio(audio_data)
            
            # Save audio file
            sf.write(
                str(output_path),
                audio_data.T,
                Config.SAMPLE_RATE,
                format=Config.EXPORT_FORMAT,
                subtype='FLOAT'
            )
            logger.info("Audio saved successfully")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error saving audio: {str(e)}")
            raise

    def normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to prevent clipping while preserving stereo balance."""
        try:
            max_val = np.max(np.abs(audio_data))
            
            if max_val > 0:
                logger.info(f"Normalizing audio (max value: {max_val})")
                return audio_data / max_val * 0.9
            return audio_data
            
        except Exception as e:
            logger.error(f"Error normalizing audio: {str(e)}")
            raise
