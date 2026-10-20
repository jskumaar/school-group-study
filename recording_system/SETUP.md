# Setup & Installation Guide

## System Requirements

- **OS**: macOS 10.15+ or Linux (Ubuntu 18.04+, Debian, Fedora, etc.)
- **Python**: 3.8 or later
- **Disk Space**: 1–2 GB for dependencies + recording storage
- **RAM**: 4 GB minimum (8 GB recommended for smooth performance)

## Step-by-Step Installation

### 1. Install Python 3

#### macOS
```bash
# Using Homebrew (recommended)
brew install python@3.11

# Or download from python.org
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# Fedora
sudo dnf install python3 python3-pip
```

### 2. Install FFmpeg

#### macOS
```bash
brew install ffmpeg
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### 3. Clone/Download Repository

```bash
cd ~/Documents/GitHub/falk_study/recording_system
```

### 4. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# On Windows: venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed opencv-python-4.8.x sounddevice-0.4.x ...
```

### 6. Verify Installation

```bash
python3 -c "import cv2, sounddevice, scipy; print('All imports OK!')"
ffmpeg -version | head -1
```

### 7. macOS: Grant Camera & Microphone Permissions

1. Open **System Settings** (or System Preferences on older macOS)
2. Go to **Privacy & Security** → **Camera**
3. Click the lock icon to make changes
4. Add **Terminal** (or your Python IDE) to the allowed apps
5. Repeat for **Microphone** tab

This grants Python full access to your camera and microphone.

## First Run

```bash
python main.py
```

You should see:
```
=====================================
 CMU Child Collaboration Study — Recorder v1.0
=====================================

[1] Discover & assign devices
[2] Run pre-session hardware check
[3] Run dominant speaker consistency check
[4] Run camera calibration
[5] Start recording session
[6] Find sync offset (Insta360 alignment)
[Q] Quit

Select an option [default: Q]:
```

## Hardware Connections

Before starting:

1. **Connect all 3 USB webcams** to available USB ports
2. **Connect Insta360 camera** via USB (enable Webcam Mode on the camera)
3. **Connect lavalier mic receivers** (DJI Mic 2 or similar) via USB
4. **Wait 5–10 seconds** for all devices to be recognized by the OS

## Testing Device Discovery

Run Option 1 from the menu to verify all devices are detected:

```
[1] Discover & assign devices
```

Expected output for lab setup with 3 webcams + 3 mics:
```
VIDEO DEVICES
[0] FaceTime Camera
[1] USB Camera - Front
[2] USB Camera - Side
[3] USB Camera - Wide

AUDIO INPUT DEVICES
[0] Built-in Microphone
[1] DJI Mic 2 (Receiver) - Left
[2] DJI Mic 2 (Receiver) - Right  
[3] DJI Mic (USB)
[4] Insta360 X4 Audio
```

Then assign:
- Webcam 1 → 1
- Webcam 2 → 2
- Webcam 3 → 3
- Mic 1 → 1
- Mic 2 → 2
- Mic 3 → 3

Assignments are saved for future sessions.

## First Full Test

After setting up hardware:

1. Run **Option 2**: Hardware Check (5-minute test)
   - All devices should report ✅ OK
   
2. Run **Option 3**: Dominance Check (15-second recording)
   - Ensures lavalier mics are picking up the right people
   
3. Run **Option 5**: Start a 1-minute test recording
   - Verify output files appear in `outputs/SESSION_*/`

## Troubleshooting Installation

### "No module named 'cv2'"

```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall opencv
pip install --upgrade opencv-python
```

### "ImportError: sounddevice"

```bash
pip install sounddevice soundfile
```

### macOS: "Permission denied" on camera

1. Open **System Settings** → **Privacy & Security**
2. Unlock the padlock
3. Ensure Terminal (or IDE) is listed under **Camera** and **Microphone**
4. Restart Terminal or IDE

### Linux: "Cannot open camera: permission denied"

```bash
# Add your user to the video and audio groups
sudo usermod -a -G video $USER
sudo usermod -a -G audio $USER

# Log out and back in
# Then restart Terminal and try again
```

## Configuration for Lab Setup

Edit `config.py` if needed:

```python
# Standard lab setup (recommended):
TARGET_FPS = 30              # 30 fps @ 1280x720 is standard
RESOLUTION = (1280, 720)     # Full HD, most USB cameras support this

# If you have older/slower computers, reduce to:
# TARGET_FPS = 20
# RESOLUTION = (1024, 576)
```

## USB Hub Recommendations

For 3 cameras + 3 mics on a single computer:

- **Recommended**: Powered USB 3.0 hub (7+ ports)
  - Each full-res camera needs ~20 Mbps
  - Total: 60 Mbps video + 1.4 Mbps audio = ~62 Mbps (fits on USB 3.0: 400 Mbps)

- **Avoid**: Unpowered USB 2.0 hubs
  - USB 2.0 max: 480 Mbps shared, will cause frame drops

## Quick Reference

| Task | Command |
|------|---------|
| Start main menu | `python main.py` |
| Just device discovery | `python device_checker.py` |
| Just audio check | `python audio_checker.py` |
| Just calibration | `python calibration.py` |
| Find sync offset | `python sync_finder.py` |
| Activate venv | `source venv/bin/activate` |
| Deactivate venv | `deactivate` |
| List installed packages | `pip list` |
| Update all packages | `pip install --upgrade -r requirements.txt` |

## Next Steps

1. **Calibrate cameras** (Option 4) — optional but recommended for 3D analysis
2. **Run a test recording** (Option 5) to verify output quality
3. **Check video files** in `outputs/SESSION_*/` to ensure quality
4. **Back up calibration files** from `calibration/` folder

## Questions or Issues?

- Review the main [README.md](README.md) for troubleshooting
- Check terminal output for specific error messages (printed in red)
- Verify all dependencies: `pip list | grep -E "opencv|sound|scipy|numpy|rich"`

---

**Ready to go!** Launch the system with:
```bash
python main.py
```
