"""
Configuration for the child collaboration study recording system.
Adjust these settings before running a session.
"""

import os
from pathlib import Path

# ==================== VIDEO SETTINGS ====================
TARGET_FPS = 30
RESOLUTION = (1280, 720)
VIDEO_CODEC = 'mp4v'  # H.264, works on macOS and Linux

# ==================== AUDIO SETTINGS ====================
AUDIO_SAMPLERATE = 44100
AUDIO_CHANNELS = 2  # stereo for DJI Mic receivers (can be separated into mono per channel)
AUDIO_DTYPE = 'float32'  # float32 for better quality and flexibility
AUDIO_SEPARATE_CHANNELS = True  # separate stereo channels into individual files

# ==================== DJI MIC SETTINGS ====================
DJI_MIC_FILTER_ENABLED = True  # only allow DJI Mic devices
DJI_MIC_KEYWORDS = ['dji', 'mic']  # case-insensitive device name matching
MAX_DJI_MIC_DEVICES = 4  # support up to 4 DJI Mics (e.g., 2 stereo receivers or 4 mono receivers)

# ==================== CAMERA CALIBRATION ====================
CHECKERBOARD_SIZE = (9, 6)  # (columns, rows)
CHECKERBOARD_SQUARE_SIZE = 0.025  # meters (25mm squares)
CALIBRATION_FRAMES_NEEDED = 15

# ==================== SESSION SETTINGS ====================
OUTPUT_BASE_DIR = "outputs"
SYNC_TONE_ENABLED = True
SYNC_TONE_FREQUENCY = 1000  # Hz
SYNC_TONE_DURATION = 0.2  # seconds per beep
SYNC_TONE_NUM_BEEPS = 3
SYNC_TONE_GAP = 0.2  # gap between beeps

# ==================== INSTA360 SETTINGS ====================
# NOTE: Insta360 is manually controlled. This is for reference only.
INSTA360_MANUAL_ONLY = True
INSTA360_SYNC_MARKER = "beep"  # audio sync marker

# ==================== DEVICE ASSIGNMENTS ====================
# These will be populated by device_checker.py after user assignment
# Mics can be assigned as stereo receivers (one device, 2 channels) or mono receivers
DEVICE_ASSIGNMENTS = {
    'webcam_1': None,  # device index
    'webcam_2': None,
    'webcam_3': None,
    # DJI Mic assignments - flexible structure:
    # Format: 'dji_mic_1': {'device': 0, 'channels': 2, 'receiver': 'Receiver 1 (2 Mics)'}
    # Can have stereo (2 channels) or mono (1 channel) devices
}

# ==================== PATHS ====================
PROJECT_ROOT = Path(__file__).parent
CALIBRATION_DIR = PROJECT_ROOT / "calibration"
OUTPUTS_DIR = PROJECT_ROOT / OUTPUT_BASE_DIR

# Ensure directories exist
CALIBRATION_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# ==================== AUDIO CHECK SETTINGS ====================
VOICE_BASELINE_DURATION = 15  # seconds
VOICE_BASELINE_WINDOW = 0.5  # seconds (for dominance analysis)
DOMINANCE_THRESHOLD_PCT = 0.75  # 75% dominance = good
CROSSTALK_WARNING_DB = 10  # if target mic not 10dB above others, warn
CHANNEL_SEPARATION_TARGET_DB = 15  # target separation between channels of same device

# ==================== LOGGING ====================
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
VERBOSE_MODE = True  # print more detailed progress

# ==================== PERFORMANCE ====================
FRAME_QUEUE_SIZE = 10  # frames to buffer per thread
AUDIO_CHUNK_SIZE = 2048  # samples per read
