# Developer Notes & Maintenance Guide

This document is for developers maintaining or extending the recording system.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    main.py (Menu)                           │
│            Interactive CLI, device assignment                │
└─────────────────┬───────────────────────────────────────────┘
                  │
      ┌───────────┼───────────┬────────────┬─────────────┐
      │           │           │            │             │
      ▼           ▼           ▼            ▼             ▼
┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐
│  device_ │ │ audio_ │ │calibra─  │ │ recorder │ │ sync_  │
│ checker  │ │checker │ │ tion     │ │          │ │ finder │
└────┬─────┘ └────┬───┘ └────┬─────┘ └────┬─────┘ └────┬───┘
     │            │           │            │            │
     ▼            ▼           ▼            ▼            ▼
 ┌─────────────────────────────────────────────────────────┐
 │           utils.py (Shared Utilities)                  │
 │  Logging, UI, audio processing, file operations       │
 └──────────────────┬──────────────────────────────────────┘
                    │
                    ▼
 ┌──────────────────────────────────────────────────────────┐
 │           config.py (Configuration)                     │
 │  All settings: FPS, resolution, sample rate, paths      │
 └──────────────────────────────────────────────────────────┘
```

---

## 📁 Module Breakdown

### `config.py`
- **Purpose**: Centralized configuration
- **Changes**: Modify here to change FPS, resolution, audio sample rate, etc.
- **Usage**: Imported by all other modules
- **Dependencies**: None (dependency-free)

### `utils.py`
- **Purpose**: Shared utilities and helpers
- **Functions**: Logging, UI formatting, audio processing, file operations
- **Key Classes**: None (all functions)
- **Dependencies**: numpy, scipy, rich, sounddevice, soundfile
- **Notes**: Good place to add new audio filters, processing functions

### `device_checker.py`
- **Purpose**: Device discovery, participant-keyed assignment, and hardware verification
- **Key Functions**:
  - `discover_video_devices()` — probe OpenCV indices 0–10
  - `discover_audio_devices()` — query sounddevice
  - `assign_participants_interactive()` — assign color labels to (cam, mic) pairs; runs paired verification panel on completion
  - `run_paired_verification()` — side-by-side panel: colored camera feed + live VU meter per participant; ENTER confirms, R redoes
  - `run_hardware_check()` — orchestrate all device checks
- **Dependencies**: cv2, sounddevice, rich
- **Output**: `device_assignments.json` with `participants` and `audio_devices` keys
- **Assignment structure**:
  ```json
  {
    "participants": [
      {"label": "red",  "cam_device": 2, "mic_device": 3, "mic_channel": 0,
       "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2}
    ],
    "audio_devices": [
      {"device": 3, "name": "DJI Mic 2 (Receiver)", "channels": 2,
       "labels": ["mic_red", "mic_blue"], "samplerate": 44100}
    ]
  }
  ```

### `audio_checker.py`
- **Purpose**: Verify lavalier mic placement and dominance
- **Key Functions**:
  - `record_voice_baseline_simultaneous()` — record 15 sec from all mics in parallel (one thread per device)
  - `analyze_dominance()` — compute dominance % per participant label
  - `analyze_crosstalk()` — measure mic separation (dB) per participant
  - `run_dominance_check()` — orchestrate full check; reads from `assignments["participants"]`
- **Dependencies**: sounddevice, numpy, scipy, rich
- **Output**: Console report (no files); reports by participant label ("red", "blue", "green")

### `calibration.py`
- **Purpose**: Camera calibration using OpenCV checkerboard
- **Key Functions**:
  - `calibrate_single_camera()` — interactive calibration workflow
  - `save_calibration()` — save to NPZ format
  - `load_calibration()` — load from NPZ format
  - `run_camera_calibration()` — orchestrate all 3 cameras
- **Dependencies**: cv2, numpy, rich, pathlib
- **Output**: `calibration/cam{1-3}_calibration.npz`
- **Notes**: 
  - Uses cv2.findChessboardCorners() for detection
  - User manually captures frames by pressing SPACE
  - Saves camera matrix + distortion coefficients

### `recorder.py`
- **Purpose**: Main simultaneous recording logic
- **Key Classes**:
  - `WebcamRecorder(threading.Thread)` — video capture thread; takes `label: str`, writes `cam_{label}.mp4`
  - `AudioRecorder` — audio capture with queue + writer thread for incremental disk writes; stereo DJI receiver split writes L → `mic_{label}.wav`, R → `mic_{label2}.wav`
- **Key Functions**:
  - `play_sync_tone()` — play 3-beep sync marker
  - `run_recording_session()` — reads `assignments["participants"]` and `assignments["audio_devices"]`; shows colored live preview; returns session path
- **Dependencies**: cv2, numpy, sounddevice, soundfile, threading, rich
- **Output**: `outputs/SESSION_YYYYMMDD_HHMMSS/{cam_{label}.mp4, mic_{label}.wav, session_log.json}`
- **Threading Model**:
  - One `WebcamRecorder` thread per participant
  - One `AudioRecorder` per unique audio device (may serve multiple participants via channel split)
  - Main thread: OpenCV preview loop + Q-key detection
  - Coordination via shared `threading.Event(stop_event)`
- **Notes**:
  - `AudioRecorder` queue maxsize=500 → ~2 min of audio buffered at most; writer thread drains to disk in real time
  - Graceful shutdown: stream closed first, then writer drains remaining queue before exit

### `sync_finder.py`
- **Purpose**: Post-recording sync offset analysis
- **Key Functions**:
  - `find_sync_offset()` — cross-correlate two audio files
  - `main()` — CLI interface
- **Dependencies**: soundfile, numpy, scipy, rich
- **Output**: Offset in seconds + correlation coefficient
- **Algorithm**: scipy.signal.correlate() for finding peak
- **Notes**: Can be run standalone or from main menu

### `main.py`
- **Purpose**: Interactive CLI menu system
- **Key Functions**:
  - `print_main_menu()` — display menu
  - `menu_discover_devices()` → calls device_checker
  - `menu_hardware_check()` → calls device_checker
  - `menu_dominance_check()` → calls audio_checker
  - `menu_camera_calibration()` → calls calibration
  - `menu_start_recording()` → calls recorder
  - `menu_sync_finder()` → calls sync_finder
- **Dependencies**: All other modules
- **Workflow**: Load assignments from JSON, present menu, call appropriate module
- **Notes**: Entry point for entire system

---

## 🔄 Data Flow

### Device Assignment Flow:
```
User runs main.py
→ Option 1: Discover & Assign
→ discover_video_devices() [probes 0-10]
→ discover_audio_devices() [queries sounddevice]
→ assign_devices_interactive() [user selects]
→ Save to device_assignments.json
```

### Recording Flow:
```
User runs main.py
→ Option 5: Start Recording
→ Load device_assignments.json
→ Pre-session checklist (user confirms)
→ run_recording_session()
  → Create SESSION folder
  → Display Insta360 reminder
  → play_sync_tone() [audio]
  → Start WebcamRecorder threads (3)
  → Start AudioRecorder threads (3)
  → Main thread: wait for Q or CTRL+C
  → Signal stop_event
  → Join all threads
  → Save session_log.json
  → Display summary
```

---

## 🛠️ Common Modifications

### Add a New Device Type

1. Add to `device_checker.py`:
   ```python
   def discover_custom_devices():
       # Your discovery logic
       return devices_list
   ```

2. Add to `recorder.py`:
   ```python
   class CustomRecorder(threading.Thread):
       def run(self):
           # Your recording logic
   ```

3. Add to `main.py`:
   ```python
   def menu_new_option():
       # Call your new code
   ```

### Reduce File Size

Edit `config.py`:
```python
RESOLUTION = (1024, 576)  # Instead of (1280, 720)
TARGET_FPS = 20           # Instead of 30
```

### Change Audio Sample Rate

Edit `config.py`:
```python
AUDIO_SAMPLERATE = 48000  # Instead of 44100
```

### Disable Sync Beep

Edit `config.py`:
```python
SYNC_TONE_ENABLED = False
```

### Add More Cameras

Edit `recorder.py` and `device_checker.py`:
- Loop from 1-N instead of 1-3
- Update config.py to support N cameras
- Adjust UI layout if displaying previews

---

## 🧪 Testing Checklist

### Before Release

- [ ] Install fresh Python environment
- [ ] Run through all menu options
- [ ] Verify device discovery works
- [ ] Verify hardware check completes
- [ ] Record a 1-minute test session
- [ ] Check output files are created with correct names
- [ ] Check session_log.json is valid JSON
- [ ] Run sync_finder on test recording
- [ ] Check all error messages are clear and actionable
- [ ] Verify all documentation is accurate

### Manual Testing Script

```bash
# Setup
python3 -m venv test_venv
source test_venv/bin/activate
pip install -r requirements.txt

# Test each module
python3 -c "import device_checker; print('device_checker OK')"
python3 -c "import audio_checker; print('audio_checker OK')"
python3 -c "import calibration; print('calibration OK')"
python3 -c "import recorder; print('recorder OK')"
python3 -c "import sync_finder; print('sync_finder OK')"

# Test main menu
python3 main.py
```

---

## 📊 Performance Considerations

### CPU Usage During Recording
- Each webcam encoding: ~10–20% per core (H.264 is compute-intensive)
- Audio recording: < 1% per stream
- **Total**: 30–70% CPU with 3 cameras on modern machine

### Memory Usage
- Each camera buffer: ~5–10 MB (queue of 10 frames)
- Audio buffer: ~1 MB per mic
- **Total**: ~50 MB baseline

### Disk I/O
- 3 cameras @ 1280×720 @ 30fps: ~450 MB/min
- Ensure SSD or fast external drive for smooth recording

### Bandwidth (if using USB hub)
- 3 cameras @ 1280×720: ~60 Mbps
- USB 3.0 hub recommended (theoretical max 400 Mbps)
- Avoid USB 2.0 hubs (max 480 Mbps shared)

---

## 🐛 Debugging Tips

### Enable Debug Logging

Edit `config.py`:
```python
LOG_LEVEL = "DEBUG"
VERBOSE_MODE = True
```

### Check Device Indices

```bash
# macOS
system_profiler SPUSBDataType

# Linux
lsusb
```

### Test Individual Modules

```bash
# Test device discovery only
python device_checker.py

# Test audio recording only
python -c "from audio_checker import run_dominance_check; run_dominance_check([1,2,3])"

# Test calibration only
python calibration.py
```

### Inspect Session Log

```bash
cat outputs/SESSION_*/session_log.json | python -m json.tool
```

---

## 📝 Code Style Guidelines

- **Python version**: 3.8+ (match setup.py)
- **Indentation**: 4 spaces (not tabs)
- **Line length**: 100 characters (preferred), 120 max
- **Naming**:
  - Functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_CASE`
  - Private: `_leading_underscore`
- **Docstrings**: Google style (Args, Returns, Raises)
- **Type hints**: Use where helpful, not required
- **Comments**: Explain "why", not "what"

### Example Function:

```python
def process_audio(audio_data: np.ndarray, sr: int = 44100) -> float:
    """
    Process audio data and return RMS level in dB.
    
    Args:
        audio_data: numpy array of audio samples
        sr: sample rate in Hz
    
    Returns:
        RMS level in dBFS (range -∞ to 0)
    
    Raises:
        ValueError: if audio_data is empty
    """
    if len(audio_data) == 0:
        raise ValueError("audio_data cannot be empty")
    
    # Compute RMS (root mean square) of audio
    rms = np.sqrt(np.mean(audio_data ** 2))
    
    # Convert to dB (20 * log10(rms / 1.0))
    db = 20 * np.log10(rms + 1e-10)  # Add epsilon to avoid log(0)
    
    return db
```

---

## 🔐 Security & Privacy

### Considerations:
1. **File permissions**: Session files are world-readable by default
   - Consider adding: `os.chmod(session_folder, 0o700)` for privacy
2. **Audio sensitivity**: Captured audio may contain sensitive information
   - Ensure proper storage and deletion after study
3. **Video footage**: May contain identifiable information
   - Follow institutional IRB requirements for storage
4. **Device info**: Saved with each session
   - Consider redacting before sharing data

---

## 📦 Dependency Management

### Current Dependencies:

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| opencv-python | >=4.8 | Video capture, calibration | ~200 MB install |
| sounddevice | >=0.4.6 | Audio input/output | Lightweight |
| soundfile | >=0.12 | WAV file I/O | Depends on libsndfile |
| numpy | >=1.24 | Array operations | Core dependency |
| scipy | >=1.10 | Signal processing | For cross-correlation |
| rich | >=13.0 | Terminal UI | Pretty formatting |
| pyaudio | >=0.2.13 | Audio (fallback) | Optional, not strictly needed |
| ffmpeg-python | >=0.2.0 | FFmpeg wrapper | For future muxing |

### To Update:
```bash
pip install --upgrade -r requirements.txt
```

### To Freeze Current Versions:
```bash
pip freeze > requirements_locked.txt
```

---

## 🔗 External Dependencies

- **FFmpeg**: Required for post-processing, not for recording
  - macOS: `brew install ffmpeg`
  - Linux: `apt-get install ffmpeg` or `dnf install ffmpeg`
- **OpenCV (cv2)**: Includes all video capture backends
  - Precompiled wheels available for macOS/Linux
  - No system-level OpenCV library needed

---

## 📚 References & Resources

### OpenCV Documentation:
- VideoCapture: https://docs.opencv.org/master/d8/dfe/classcv_1_1VideoCapture.html
- Calibration: https://docs.opencv.org/master/d9/d0c/group__calib3d.html
- Checkerboard detection: https://docs.opencv.org/master/d9/d0c/group__calib3d.html#gadc8dbf1d8c45f538c0467d578d9eb80b

### SoundDevice Documentation:
- Recording: https://python-sounddevice.readthedocs.io/
- Query devices: https://python-sounddevice.readthedocs.io/en/stable/api/functions.html#sounddevice.query_devices

### SciPy Signal Processing:
- Cross-correlation: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html

### Rich Documentation:
- Terminal UI: https://rich.readthedocs.io/

---

## 🚀 Future Roadmap

### Short-term (v1.1)
- [ ] Add simultaneous audio recording (true parallel threads)
- [ ] Add fisheye calibration for Insta360
- [ ] Add real-time multi-window preview grid

### Medium-term (v2.0)
- [ ] GUI version using PyQt5/PySide6
- [ ] Support for arbitrary number of cameras/mics
- [ ] Auto-muxing after recording completes
- [ ] Cloud backup integration

### Long-term (v3.0)
- [ ] Real-time 3D pose estimation (MediaPipe integration)
- [ ] Web interface for remote monitoring
- [ ] Mobile app for session status
- [ ] Database for study metadata

---

## 🤝 Contributing

To contribute improvements:

1. Create a new branch: `git checkout -b feature/your-feature`
2. Make changes following code style guidelines
3. Test thoroughly: `python main.py` through all options
4. Write/update documentation
5. Commit with clear message: `git commit -m "Add feature X"`
6. Push and create pull request

---

## 📄 License & Attribution

This project is provided for Carnegie Mellon University child collaboration research.

---

**Last Updated**: April 2026  
**Maintainer**: CMU Child Collaboration Study Lab  
**Version**: 1.0
