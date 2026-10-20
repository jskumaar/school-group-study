# CMU Child Collaboration Study — Multi-Device Recording System

A Python-based recording system for simultaneous capture of video from 3 webcams, audio from 3 lavalier microphones (DJI Mic), and manual recording from an Insta360 camera. Designed for child collaboration research in laboratory settings.

## Features

- **Participant-keyed assignment**: Devices are assigned by participant color label (red, blue, green), not generic numbered slots. Files are named `cam_red.mp4`, `mic_red.wav`, etc. — pairing is explicit and permanent.
- **Paired verification panel**: Before each session, a side-by-side panel shows each participant's camera feed (colored border) with a live VU meter for their mic. Confirm that the right camera is watching the right child before recording begins.
- **Simultaneous recording**: All webcams and lavalier mics run in parallel threads, captured to disk incrementally.
- **DJI Mic 2 stereo splitting**: When using the DJI Mic 2 receiver (stereo USB), the two transmitter channels are split into separate WAV files automatically.
- **Pre-session hardware check**: Real-time verification of camera resolutions, frame rates, and audio levels.
- **Dominant speaker consistency check**: Confirms each lavalier mic primarily captures one child's voice.
- **Camera calibration**: OpenCV checkerboard calibration for the webcams (optional).
- **Sync beep**: 3-beep audio marker at session start for post-processing alignment.
- **Live recording preview**: Colored per-participant camera feeds shown during recording; press Q to stop.
- **Session logging**: JSON metadata for every session.
- **Sync finder**: Cross-correlates Insta360 audio with lavalier mics to find timing offset.

## Requirements

### Hardware
- macOS (primary) or Linux
- 3 USB webcams (placed behind each child's head for gaze capture)
- 3 lavalier microphones via DJI Mic 2 receiver (stereo) or individual Bluetooth units
- 1 Insta360 camera (X3, X4, or compatible)
- ~500 MB–1 GB storage per minute of multi-camera recording

### Software
- Python 3.8+
- FFmpeg (for post-processing muxing)

### macOS-Specific Setup

Grant Camera & Microphone Access:
1. Open **System Settings → Privacy & Security**
2. Under **Camera**, add Terminal (or your Python app)
3. Repeat for **Microphone**

### Linux Setup

```bash
sudo usermod -a -G audio $USER
# Log out and back in for changes to take effect
```

## Installation

1. Navigate to the `recording_system/` folder.

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Verify FFmpeg:
   ```bash
   ffmpeg -version
   ```
   Install if missing:
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt-get install ffmpeg`

## Quick Start

```bash
python main.py
```

This launches the interactive menu:

```
[1] Discover & assign devices
[2] Run pre-session hardware check
[3] Run dominant speaker consistency check
[4] Run camera calibration
[5] Start recording session
[6] Mux last session (cam video + mic audio)
[7] Find sync offset (Insta360 alignment)
[Q] Quit
```

## Step-by-Step Usage

### Option 1 — Discover & Assign Devices

The system scans all connected USB video and audio devices. You then:

1. Choose how many participants (e.g., 3)
2. Choose a color label for each participant (red, blue, green)
3. For each participant, identify:
   - Their **webcam** (a preview grid helps you confirm which index is which camera)
   - Their **DJI mic** (device index + which channel: L or R for stereo receivers)
4. A **paired verification panel** opens showing all participants side-by-side:
   - Each column has a colored label banner, a camera feed with a thick colored border, and a live VU meter for that participant's mic
   - Press **ENTER** to confirm assignments, **R** to redo, **Q/ESC** to cancel

Assignments are saved to `device_assignments.json` for future sessions.

### Option 2 — Hardware Check

Runs a 3–5 second test on all assigned devices:

- **Webcams**: checks resolution (target 1280×720) and frame rate (target 30 fps)
- **Mics**: records 3 seconds, displays RMS level per participant

Example output:
```
PRE-SESSION CHECK RESULTS

VIDEO DEVICES
  ✅ red  (dev 2): 1280x720 @ 30.0 fps
  ✅ blue (dev 0): 1280x720 @ 30.0 fps
  ✅ green (dev 1): 1280x720 @ 29.8 fps

AUDIO DEVICES
  ✅ mic_red  (DJI Mic 2, L): avg -18.2 dBFS
  ✅ mic_blue (DJI Mic 2, R): avg -20.5 dBFS
  ⚠️  mic_green (DJI Mic BT): avg -38.1 dBFS — below -35 dBFS
```

### Option 3 — Dominant Speaker Consistency Check

Confirms mic placement before recording:

1. Records 15 seconds from all participant mics simultaneously
2. Segments audio into 0.5-second windows
3. Reports which mic is dominant per window, and crosstalk ratio

**What to do**: Ask each child to say their name and a few sentences while you observe the dominance table. Each mic should dominate ≥ 75% of its windows. If < 50%, reposition the mic closer to that child's mouth.

Example output:
```
┌──────────┬─────────────┬─────────────────┬──────────────┐
│ Mic      │ Dominant in │ Crosstalk ratio │ Status       │
├──────────┼─────────────┼─────────────────┼──────────────┤
│ red      │ 82.0%       │ +14.2 dB        │ ✅ Good      │
│ blue     │ 74.0%       │ +11.8 dB        │ ✅ Good      │
│ green    │ 44.0%       │  +6.3 dB        │ ❌ High CT   │
└──────────┴─────────────┴─────────────────┴──────────────┘
```

### Option 4 — Camera Calibration

Optional OpenCV checkerboard calibration per webcam. Hold a printed 9×6 checkerboard in front of each camera, press SPACE to capture frames (need 15+), then ESC. Saves calibration `.npz` files for 3D analysis.

**Note**: Calibration is optional — skip it unless you plan 3D pose estimation.

### Option 5 — Start Recording Session

1. A pre-session checklist confirms cameras are positioned, mics are clipped, etc.
2. A prompt reminds you to **start Insta360 recording manually**
3. Once you press ENTER, all devices begin recording simultaneously
4. A 3-beep sync tone plays (captured by all mics and the Insta360)
5. A live preview window shows all camera feeds with participant-colored borders
6. Press **Q** in the preview window to stop

**Output folder:**
```
outputs/SESSION_20250101_120000/
├── cam_red.mp4        # Webcam assigned to "red" participant
├── cam_blue.mp4       # Webcam assigned to "blue" participant
├── cam_green.mp4      # Webcam assigned to "green" participant
├── mic_red.wav        # Lavalier mic for "red"
├── mic_blue.wav       # Lavalier mic for "blue"
├── mic_green.wav      # Lavalier mic for "green"
└── session_log.json   # Timestamps, device info, stream counts
```

### Option 6 — Mux Last Session

Pairs each `cam_{label}.mp4` with its `mic_{label}.wav` using FFmpeg. Produces:
```
cam_red_muxed.mp4
cam_blue_muxed.mp4
cam_green_muxed.mp4
```

### Option 7 — Find Sync Offset (Insta360 Alignment)

After exporting audio from your Insta360:

1. Provide path to Insta360 audio WAV
2. Provide path to any lavalier mic WAV (e.g., `mic_red.wav`)
3. Tool cross-correlates the 3-beep sync tone to find timing offset
4. Outputs offset in seconds and an FFmpeg trim command for alignment

## Device-Specific Setup

### DJI Mic 2

- **Stereo receiver** (2 transmitters → L+R channels): Detected as one stereo USB device. The system automatically splits L → `mic_red.wav`, R → `mic_blue.wav` (or whichever labels you assigned to channels 0 and 1).
- **Individual Bluetooth units**: Each appears as a separate mono device; assign each to a participant.
- Ensure transmitters are paired and powered before launching the script.

### Insta360 X3/X4

1. Enable **Webcam Mode** on the camera: Settings → Connectivity → Webcam Mode → ON, or use the Insta360 Link desktop app.
2. The system does NOT control the Insta360 — start and stop it manually.
3. The 3-beep sync tone is the alignment reference for post-processing.

## Troubleshooting

### "Cannot open camera" Error
- Verify the device index is correct (re-run Option 1)
- On macOS: grant Terminal camera permission in System Settings → Privacy → Camera
- Try a different USB port

### Very Low Audio Levels (< −40 dBFS)
- Check microphone is powered on and not muted
- Ensure USB connector is fully seated
- Test with system audio settings

### Low Webcam FPS (< 25 fps)
- Reduce resolution in `config.py` (try `(1024, 576)`)
- Use a powered USB 3.0 hub (unpowered hubs cause bandwidth contention with 3 cameras)

### "No module named 'cv2'" or Similar
- Ensure virtual environment is activated: `source venv/bin/activate`
- Re-run `pip install -r requirements.txt`

### Sync Beep Not Audible
- Check system volume
- On macOS: System Settings → Sound → Output

### Paired Verification Panel Shows Wrong Camera for a Participant
- Press **R** to redo assignment
- Re-run Option 1 and reassign

## Configuration

Edit `config.py` to customize:

```python
TARGET_FPS = 30                    # webcam frame rate target
RESOLUTION = (1280, 720)           # video resolution (width × height)
AUDIO_SAMPLERATE = 44100           # audio sample rate (Hz)
SYNC_TONE_ENABLED = True           # play 3-beep marker at session start
SYNC_TONE_FREQUENCY = 1000         # beep frequency (Hz)
DOMINANCE_THRESHOLD_PCT = 0.75     # acceptable dominance (75%)
CROSSTALK_WARNING_DB = 10          # crosstalk warning threshold
```

## Post-Processing

### Mux Video + Audio

Use Option 6 in the menu, or manually:
```bash
ffmpeg -i cam_red.mp4 -i mic_red.wav -c:v copy -c:a aac -shortest cam_red_muxed.mp4
ffmpeg -i cam_blue.mp4 -i mic_blue.wav -c:v copy -c:a aac -shortest cam_blue_muxed.mp4
ffmpeg -i cam_green.mp4 -i mic_green.wav -c:v copy -c:a aac -shortest cam_green_muxed.mp4
```

### Align Insta360

1. Export Insta360 audio as WAV from the Insta360 app
2. Run Option 7 (Sync Finder) or `python sync_finder.py`
3. Apply the offset in DaVinci Resolve, Adobe Premiere, or FFmpeg

## Project Structure

```
recording_system/
├── main.py              # Entry point: interactive menu
├── config.py            # Configuration settings
├── utils.py             # Shared utilities: UI, audio processing, file ops
├── device_checker.py    # Device discovery, participant assignment, verification panel
├── audio_checker.py     # Dominant speaker consistency analysis
├── calibration.py       # Camera calibration (OpenCV checkerboard)
├── recorder.py          # Simultaneous recording logic
├── sync_finder.py       # Post-recording: find Insta360 sync offset
├── requirements.txt     # Python package dependencies
├── outputs/             # Runtime: session folders (auto-created, timestamped)
└── calibration/         # Runtime: camera calibration files (.npz)
```

## Performance Notes

- **Storage**: At 1280×720 @ 30fps, each webcam uses ~150 MB/min. Three webcams + three audio streams ≈ 450 MB/min.
- **CPU**: H.264 encoding is CPU-intensive. On older machines, reduce resolution or frame rate in `config.py`.
- **USB bandwidth**: Three cameras at full resolution may saturate a USB 2.0 bus. Use a powered USB 3.0 hub.

## License

Provided for research purposes at Carnegie Mellon University. Modify and use as needed for your study.

---

**Last Updated**: April 2026