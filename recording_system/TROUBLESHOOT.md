# Troubleshooting Quick Guide

**Having problems? Use this guide to fix common issues quickly.**

---

## 🔴 Recording Won't Start

### Symptom: Error message when starting recording

**Checklist:**
- [ ] All USB cables connected?
- [ ] All devices powered on?
- [ ] Ran hardware check first (Option 2)?
- [ ] Insta360 Webcam Mode enabled?

**Solutions:**
1. Unplug all USB devices, wait 10 seconds, plug back in
2. Restart Python: `python main.py`
3. Try Option 2 (Hardware Check) first
4. Check terminal output for specific error messages

**See:** [README.md](README.md#troubleshooting)

---

## 🎥 Camera Issues

### "Cannot open camera" Error
```
[ERROR] ❌ Webcam 1: Cannot open camera 0
```

**Fix:**
1. Verify cable connection (try different USB port)
2. Test camera with system settings or Photo app
3. Restart Python after physically reconnecting
4. On macOS: Grant Terminal camera permission
5. Re-run Option 1 (Device Discovery) — device index may have changed

### Low Frame Rate (FPS)
```
⚠️ Camera 1: 12 fps (target 30)
```

**Fix:**
1. Close other USB-heavy apps (browser, streaming, etc.)
2. Reduce resolution: edit `config.py`
   ```python
   RESOLUTION = (1024, 576)  # instead of (1280, 720)
   ```
3. Try USB 3.0 hub instead of USB 2.0
4. Test with one camera only

### Blurry Video
- Manual focus on webcam (if available)
- Increase lighting in recording area
- Move camera closer to subjects
- Clean camera lens

---

## 🎤 Microphone Issues

### Audio Too Quiet (< -40 dBFS)
```
❌ Mic 1: Silent — avg -62 dBFS
```

**Fix:**
1. Check mic is powered on (DJI Mic 2: LED should be on)
2. Check mic is not muted (feel for mute switch)
3. Check volume knob (if present) is not at 0%
4. Try different USB port
5. Check Windows/macOS volume settings
6. Test mic with Voice Memos app or system audio

### Audio Too Loud (> -3 dBFS)
```
⚠️ Mic 1: Clipping detected (too loud)
```

**Fix:**
1. Reduce microphone volume (if controllable)
2. Move mic away from speaker's mouth slightly
3. Check for ambient noise (loud fan, music, etc.)
4. Test in quieter location

### No Audio Device Showing Up
- Plug in USB receiver/mic
- Wait 5 seconds for OS recognition
- Try different USB port
- Restart Python

---

## 💾 Storage & Disk Space

### "Disk full" Error
```
Error: Insufficient disk space
```

**Fix:**
1. Check available space: `df -h` (macOS/Linux)
2. Delete old SESSION folders: `rm -rf outputs/SESSION_old*/`
3. Move recent sessions to external drive
4. Need ~500 MB per minute of recording

### Files Missing or Corrupted
- Stop recording cleanly (press Q, wait for threads to join)
- Don't unplug devices while recording
- Use SSD or fast USB drive (not slow thumb drive)
- Keep separate external drive for backups

---

## ⚠️ Permission Issues

### macOS: "Permission denied" (camera/audio)
```
Permission denied: cannot access camera
```

**Fix:**
1. Open **System Settings** (or System Preferences)
2. Go to **Privacy & Security** → **Camera**
3. Click the lock icon to unlock
4. Find and add **Terminal** to the allowed apps list
5. Repeat for **Microphone** tab
6. Restart Terminal and try again

### Linux: "Permission denied" (audio)
```
Cannot open audio device
```

**Fix:**
```bash
# Add your user to audio group
sudo usermod -a -G audio $USER

# Log out and back in
# Then restart Terminal
```

---

## 🐍 Python & Installation

### "ModuleNotFoundError: No module named 'cv2'"
```
ImportError: No module named 'cv2'
```

**Fix:**
1. Make sure virtual environment is activated:
   ```bash
   source venv/bin/activate
   ```
2. Reinstall opencv:
   ```bash
   pip install --upgrade opencv-python
   ```
3. Verify: `python -c "import cv2; print('OK')"`

### "SoundDeviceError: No device with id"
```
Error: No device with id 5
```

**Fix:**
1. Device indices may have changed (USB plug order)
2. Unplug/replug all USB devices in same order
3. Re-run Option 1 (Device Discovery) to get new indices
4. Save new assignments to device_assignments.json

### "pip: command not found"
```
bash: pip: command not found
```

**Fix:**
```bash
# Use python3 -m pip instead
python3 -m pip install -r requirements.txt
```

---

## 🎬 Recording Issues

### Recording Stops Suddenly
**Causes:**
- Disk full
- USB device unplugged
- Thermal throttling (computer overheating)
- Out of memory (RAM)

**Fix:**
1. Check free disk space: `df -h`
2. Verify USB cables are secure
3. Reduce resolution in `config.py`
4. Close other applications
5. Allow computer to cool down
6. Test with shorter recording (5 min vs 30 min)

### Sync Beep Not Audible
- Check system volume is not muted
- Verify audio output in system settings
- Try different speaker/headphones
- Check sounddevice can access output device

### Files Are Huge (Growing Too Fast)
- 1 camera @ 1280×720 @ 30fps = ~150 MB/min
- 3 cameras = ~450 MB/min = normal
- Audio files should be ~500 KB/min
- To reduce: lower resolution or frame rate in `config.py`

---

## 🔍 Post-Recording Issues

### Cannot Find Session Folder
```
Where are the output files?
```

**Answer:**
- Located in: `outputs/SESSION_YYYYMMDD_HHMMSS/`
- Example: `outputs/SESSION_20250101_120000/`
- In terminal, run: `ls -la outputs/` to list all sessions

### Sync Offset Tool Not Working
```
python sync_finder.py
→ Error: File not found
```

**Fix:**
1. Make sure both audio files exist (check file paths)
2. Files must be WAV format (not MP4)
3. Both files need to contain the sync beep (3 beeps at start)
4. Use absolute file paths: `/full/path/to/file.wav`

---

## 📱 Insta360 Issues

### Insta360 Not Showing Up As Device
```
No Insta360 audio device found
```

**Fix:**
1. Enable Webcam Mode on camera (Settings → Connectivity → Webcam Mode → ON)
2. Restart Python after enabling
3. Try USB cable first (not wireless)
4. Check official Insta360 app documentation
5. Some models need Insta360 Link desktop app running

### Insta360 Recording Offset Very Large
- Common: Insta360 may start/stop at slightly different times
- Solution: Use sync finder to calculate exact offset
- Apply offset in post-processing (DaVinci Resolve, FFmpeg, etc.)

### Audio Levels from Insta360 Are Wrong
- Insta360 may have different input gain settings
- Adjust in camera's audio settings menu
- Levels will be re-calibrated during sync finder analysis

---

## 🔧 Advanced Troubleshooting

### Check System Info
```bash
# macOS
system_profiler SPUSBDataType

# Linux
lsusb
```

### Monitor Resource Usage
```bash
# macOS
top  # Press Q to quit

# Linux
htop  # Press Q to quit
```

### Test Individual Devices
```bash
# Test device discovery
python device_checker.py

# Test audio recording
python audio_checker.py

# Test calibration
python calibration.py
```

### Enable Verbose Output
Edit `config.py`:
```python
VERBOSE_MODE = True
LOG_LEVEL = "DEBUG"
```

---

## 🆘 Still Stuck?

1. **Read the error message carefully** — it usually tells you what's wrong
2. **Search in [README.md](README.md#troubleshooting)** — most issues are covered
3. **Check [DEVELOPER.md](DEVELOPER.md)** — for code-level debugging
4. **Write down exactly:**
   - What were you doing?
   - What error did you see?
   - What have you tried?
5. **Contact lab manager** with this information

---

## ✅ Verification Checklist

If everything seems wrong, verify basics:

- [ ] Python installed: `python --version`
- [ ] Virtual environment activated: `source venv/bin/activate`
- [ ] Dependencies installed: `pip list | grep opencv`
- [ ] FFmpeg available: `ffmpeg -version`
- [ ] USB devices connected
- [ ] Devices powered on
- [ ] No error lights (mic, camera)
- [ ] Disk space available: `df -h`

---

## 📞 Quick Help

| Problem | Fast Fix | Full Guide |
|---------|----------|-----------|
| Can't find files | Look in `outputs/` folder | [README.md](README.md) |
| Camera won't open | Check USB, restart Python | [README.md](README.md#troubleshooting) |
| Audio too quiet | Check mic is on, not muted | [README.md](README.md#very-low-audio-levels) |
| Permission error | Grant camera access to Terminal | [SETUP.md](SETUP.md#macos-grant-camera--microphone-permissions) |
| Disk full | Delete old sessions, check space | This page |
| Module not found | Activate venv, reinstall | This page |

---

**Troubleshooting not helping? Ask for help!** 🙋

Start with the basics: USB connected? Powered on? Permissions OK?

Then check the detailed guides: [README.md](README.md) or [DEVELOPER.md](DEVELOPER.md)
