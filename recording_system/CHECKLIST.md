# Pre-Session Checklist & Quick Start Guide

## Before Your First Recording Session

This checklist ensures everything is ready before you start recording data.

### ✅ Software Setup (One-Time)

- [ ] Python 3.8+ installed
- [ ] Virtual environment created: `python3 -m venv venv`
- [ ] Virtual environment activated: `source venv/bin/activate`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] FFmpeg installed: `ffmpeg -version` returns version info
- [ ] macOS: Camera & Microphone permissions granted to Terminal

### ✅ Hardware Setup (One-Time or Per-Lab-Session)

- [ ] All 3 USB webcams connected and powered
- [ ] All lavalier mic receivers connected and powered (mics clipped on)
- [ ] Insta360 camera connected and Webcam Mode enabled
- [ ] USB hub is powered (if using one)
- [ ] All cables are secure and labeled
- [ ] Recording location has good lighting and minimal noise

### ✅ First-Time Device Setup (One-Time)

1. Open terminal and activate venv: `source venv/bin/activate`
2. Run: `python main.py`
3. Select **Option 1**: Discover & Assign Devices
4. Choose a color label for each participant (e.g., red, blue, green)
5. For each participant, confirm:
   - Their **webcam** (a preview grid helps you pick the right index)
   - Their **DJI mic** channel (device + L or R channel for stereo receiver)
6. A **paired verification panel** opens — check each column matches the right child
7. Press **ENTER** to confirm — assignments are saved to `device_assignments.json`

### ✅ Pre-Recording Day Checklist

**30 minutes before session:**

1. [ ] **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

2. [ ] **Run pre-session hardware check**:
   ```bash
   python main.py → Option 2: Hardware Check
   ```
   - All webcams: ✅ OK (should show 1280×720 @ 30fps)
   - All mics: ✅ OK (level should be -20 to -30 dBFS)
   - If any device shows ❌, troubleshoot before continuing

3. [ ] **Run dominant speaker check** (only if repositioning mics):
   ```bash
   python main.py → Option 3: Dominance Check
   ```
   - Ask each child to say their name and a few sentences
   - Each mic should be dominant in ~80%+ of that child's speech
   - If < 50%: reposition mic closer to child's mouth

4. [ ] **Position children and cameras**:
   - Mount all 3 webcams pointing at the collaboration area
   - Position Insta360 to capture overall activity (overhead or side view)
   - Clip lavalier mics on each child (6–8 inches below mouth, pointing toward speaker)

5. [ ] **Final equipment check**:
   - [ ] All USB cables connected
   - [ ] All devices powered on (especially Insta360)
   - [ ] Webcam focus is sharp (may need manual adjustment)
   - [ ] Lavalier mics are not muted
   - [ ] Insta360 display shows "Ready to Record"
   - [ ] Recording area is well-lit and noise-free

### ✅ Running a Recording Session

1. [ ] **Start the recording system**:
   ```bash
   python main.py
   ```

2. [ ] **Select Option 5**: Start Recording Session

3. [ ] **Follow the prompts**:
   - Confirm all equipment in checklist (select "y" for each)
   - System reminds you to start Insta360 manually
   - Click the record button on the Insta360 (or use companion app)
   - Press ENTER to begin recording

4. [ ] **Session is recording**:
   - System plays 3-beep sync tone (should be audible)
   - Sync beep is captured by all devices for alignment
   - Recording continues until you press **Q**

5. [ ] **Stop recording**:
   - When task is complete, press **Q** in the terminal
   - System stops all streams gracefully
   - Files are saved to `outputs/SESSION_YYYYMMDD_HHMMSS/`
   - System reminds you to stop Insta360

6. [ ] **Stop Insta360**:
   - Press the record button again on the camera to stop

### ✅ Post-Session Tasks

1. [ ] **Check output files**:
   ```bash
   ls -lh outputs/SESSION_*/
   ```
   - Should have: `cam_red.mp4`, `cam_blue.mp4`, `cam_green.mp4`, `mic_red.wav`, `mic_blue.wav`, `mic_green.wav` (label names match your participants)
   - File sizes: cam files ~150–200 MB/min, audio files ~500 KB/min

2. [ ] **Back up session folder**:
   - Copy entire `SESSION_*/` folder to external hard drive immediately
   - Don't rely on local disk storage

3. [ ] **Export Insta360 footage**:
   - Connect Insta360 to desktop
   - Use official Insta360 app to export video and audio as MP4 + WAV
   - Save to same session folder

4. [ ] **Find sync offset** (if using Insta360):
   ```bash
   python sync_finder.py
   ```
   - Input: path to Insta360 audio WAV
   - Input: path to any lavalier mic WAV (e.g., `mic_red.wav`)
   - Output: offset in seconds (e.g., "+2.341s")
   - Use this offset in post-processing software

5. [ ] **Optional: Mux video + audio** (use Menu Option 6, or manually):
   ```bash
   ffmpeg -i outputs/SESSION_*/cam_red.mp4 -i outputs/SESSION_*/mic_red.wav \
     -c:v copy -c:a aac -shortest cam_red_muxed.mp4
   ```

### 📋 Troubleshooting During Session

| Issue | Solution |
|-------|----------|
| Camera not detected | Check USB connection, restart Python script |
| Audio level too low | Check mic is powered, not muted, volume wheel is up |
| Webcam FPS dropping | Reduce resolution in `config.py` (1024×576 instead of 1280×720) |
| "Permission denied" on macOS | Grant Terminal camera access: System Settings → Security → Camera |
| Sync beep not audible | Check system volume, check audio output device |
| Recording stops suddenly | Check available disk space, check USB hub power |

### 🎯 Pro Tips

1. **Always test before real data**: Run a 1-minute test recording to verify quality
2. **Start Insta360 first**: Begin manual Insta360 recording before pressing ENTER in the script
3. **Label everything**: Write session number on Insta360 memory card, on mic clamps, etc.
4. **Back up immediately**: Don't leave data on lab computer overnight
5. **Keep checklist organized**: Print this checklist and check items off on paper
6. **Budget time**: Expect 10–15 minutes setup + 5 minutes breakdown per session

### 🔄 Typical Session Timeline

| Time | Task |
|------|------|
| T-0:30 | Hardware check (5 min) |
| T-0:20 | Position children and cameras |
| T-0:10 | Final equipment check |
| T-0:05 | Start Insta360 recording (manually) |
| T-0:00 | Press ENTER — Python starts recording + sync beep |
| T+5 to T+30 | Child collaboration task runs |
| T+30 | Press Q to stop recording |
| T+31 | Stop Insta360 (manually) |
| T+32 | Review files, back up to external disk |

### 📱 Quick Reference

**Quick start after first time setup:**
```bash
cd ~/Documents/GitHub/falk_study/recording_system
source venv/bin/activate
python main.py
# Select 2, then 5 (or 3 if repositioning mics)
```

**If USB devices not recognized:**
```bash
# macOS
system_profiler SPUSBDataType

# Linux
lsusb
```

**Check free disk space:**
```bash
df -h
```

---

**Questions?** See [README.md](README.md) or [SETUP.md](SETUP.md) for detailed info.

Good luck with your study! 🎓📹🎤
