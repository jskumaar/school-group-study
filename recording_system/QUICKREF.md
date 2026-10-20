# Quick Reference Card

Print this page and keep it on your desk during lab sessions!

---

## 🚀 Quick Start

```bash
cd ~/Documents/GitHub/falk_study/recording_system
source venv/bin/activate
python main.py
```

## 📋 Menu Options

| # | Option | Use When | Time |
|---|--------|----------|------|
| 1 | Discover & Assign Devices | First time or new hardware | 3 min |
| 2 | Hardware Check | Before each session | 5 min |
| 3 | Dominance Check | After repositioning mics | 15 sec |
| 4 | Calibration | Optional, one-time per camera | 10 min/cam |
| 5 | Start Recording | Ready to begin session | 5-30 min |
| 6 | Mux Last Session | After recording, to pair video+audio | 1 min |
| 7 | Sync Finder | After exporting Insta360 footage | 1 min |
| Q | Quit | Done for the day | — |

---

## ✅ Pre-Session Checklist (5 min)

- [ ] Activate venv: `source venv/bin/activate`
- [ ] Start: `python main.py` → **Option 2** (Hardware Check)
- [ ] All cameras: ✅ OK @ 1280×720 @ 30fps?
- [ ] All mics: ✅ OK @ -20 to -30 dBFS?
- [ ] Position children & cameras
- [ ] Clip lavalier mics on each child (6–8" below mouth)
- [ ] Start Insta360 recording (manually)
- [ ] Run: `python main.py` → **Option 5** (Start Recording)
- [ ] Confirm checklist items (y/y/y/y/y)
- [ ] Wait for "Press ENTER to begin..." prompt
- [ ] Press ENTER — recording starts with sync beep 🔔

---

## 🔴 During Recording

| Key | Action |
|-----|--------|
| Q | Stop all recording |

A live preview window shows each participant's camera feed (colored border) while recording. **Duration**: typically 5–30 minutes depending on your task.

---

## 🛑 Stop & Post-Session

1. Press **Q** in terminal → all devices stop
2. System prints final summary with output folder
3. Stop Insta360 manually (press record button again)
4. Backup `outputs/SESSION_*/` to external drive **NOW**
5. Export Insta360 video + audio as MP4 + WAV

---

## 🔍 Troubleshooting Quick Fixes

| Problem | Fix | Time |
|---------|-----|------|
| Camera not found | Restart Python, check USB | 30 sec |
| Audio too quiet | Check mic powered, not muted | 30 sec |
| FPS dropping | Reduce resolution in config.py | 5 min |
| Permission error (macOS) | Grant Terminal camera access | 2 min |
| Disk space full | Delete old SESSION folders | 5 min |

---

## 📁 File Locations

| Item | Location | Notes |
|------|----------|-------|
| All code | `recording_system/` | This folder |
| Settings | `config.py` | Edit to change FPS, resolution, etc. |
| Device assignments | `device_assignments.json` | Auto-saved by program |
| Session recordings | `outputs/SESSION_YYYYMMDD_HHMMSS/` | Timestamped folders |
| Camera calibration | `calibration/cam{1-3}_calibration.npz` | Optional, one-time |

---

## 🎙️ Audio Levels Reference

| Level | Status | Action |
|-------|--------|--------|
| -10 to -20 dBFS | ✅ Ideal | Good! Ready to go |
| -20 to -40 dBFS | ⚠️ Usable | Acceptable but could be louder |
| < -40 dBFS | ❌ Too quiet | Check mic connection, power, volume |
| > -3 dBFS | ❌ Clipping | Too loud, reduce mic volume |

---

## 📸 Video Quality Targets

| Metric | Target | Status |
|--------|--------|--------|
| Resolution | 1280×720 | Check hardware report |
| Frame Rate | 30 fps | Should be 29.5–30.0 fps |
| Codec | H.264 | MP4 files automatically |
| File Size | ~150–200 MB/min | Expect for 3 cameras |

---

## 🔊 Sync Beep Info

| Feature | Details |
|---------|---------|
| Tone | 1000 Hz sine wave |
| Pattern | 3 beeps × 200ms (200ms gap) |
| Captured By | All 3 lavalier mics + Insta360 audio |
| Purpose | Align footage in post-editing |
| Timing | Plays at session START |

**To find offset in post:**
```bash
python sync_finder.py
→ Input: insta360_audio.wav
→ Input: mic_red.wav   (or mic_blue.wav, etc.)
→ Output: Offset (e.g., "+2.341 seconds")
```

---

## 🎬 Post-Processing Commands

### Mux video + audio (or use Menu Option 6):
```bash
ffmpeg -i cam_red.mp4 -i mic_red.wav -c:v copy -c:a aac -shortest cam_red_muxed.mp4
```

### Find Insta360 offset:
```bash
python sync_finder.py
```

### Check file info:
```bash
ffmpeg -i cam_red.mp4
ffmpeg -i mic_red.wav
```

---

## 🚨 Emergency Stops

| Situation | Action |
|-----------|--------|
| Want to stop recording | Press **Q** in Python terminal |
| Program crashed | Press **CTRL+C** in terminal |
| Need to restart everything | Close terminal, run `python main.py` again |
| Disk running out | Stop recording, back up data to external drive |

---

## 💾 Backup Checklist

After each session:
- [ ] `outputs/SESSION_*/` copied to external drive
- [ ] Insta360 footage exported and backed up
- [ ] Check files exist on external drive
- [ ] Delete local copies only after verifying backup

**Rule: Never delete the only copy!**

---

## 🆘 Getting Help

| Issue | Resource |
|-------|----------|
| Installation problems | See `SETUP.md` |
| Using the system | See `README.md` |
| Pre-session setup | See `CHECKLIST.md` |
| Feature details | See `IMPLEMENTATION.md` |
| Installation errors | Check terminal for red error text |

---

## 📞 Common Questions

**Q: How long does recording take?**  
A: Depends on your task. Typically 5–30 minutes. System continues until you press Q.

**Q: Can I pause and resume?**  
A: No. Press Q to stop (creates one file). Start a new session to record more.

**Q: What if Insta360 crashes?**  
A: You'll still have all 3 webcams + 3 mics recorded. Just skip Insta360 in post.

**Q: Can I use different cameras?**  
A: Yes! Just re-run Option 1 to discover and assign any USB video device.

**Q: Is calibration required?**  
A: No. It's optional. Only use if doing 3D pose estimation.

---

## ⏱️ Typical Session Timeline

```
T-0:30  Hardware check: 5 min
T-0:25  Reposition children & cameras: 10 min
T-0:15  Start Insta360: 1 min
T-0:14  Run Python, confirm checklist: 5 min
T-0:09  Wait for sync beep: press ENTER
T+0:00  Recording starts 🔴
T+0-30  Child collaboration task
T+0:30  Press Q to stop ⚫
T+0:31  Back up data to external drive

TOTAL: 60 minutes lab time
```

---

## 🎓 Lab Best Practices

1. **Always test first**: Do a 1-minute test recording before real data
2. **Back up immediately**: Don't leave data on lab computer overnight
3. **Label everything**: Write session # on Insta360, mic clamps, file folders
4. **Use powered USB hub**: Unpowered hubs cause frame drops
5. **Keep cables organized**: Label and store neatly for next session
6. **Monitor disk space**: Check free space before each session
7. **Document issues**: Note any problems in session log
8. **Prepare calibration board**: Print 9×6 checkerboard on foam board

---

## 🔗 File Size Reference

What to expect per minute of recording:

| Component | Size/Min | Notes |
|-----------|----------|-------|
| 1 webcam @ 1280×720 | ~150 MB | 3 cameras = 450 MB |
| 1 lavalier mic @ 44.1kHz | ~500 KB | 3 mics = 1.5 MB |
| **Total (3+3)** | **~450 MB** | Plan storage accordingly |

**30-minute session**: ~13.5 GB of raw video/audio

---

**Print & Keep Handy! 📌**

Last updated: April 2026  
Version: 1.0
