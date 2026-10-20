# CMU Child Collaboration Study — Recording System

## 📚 Documentation Index

Welcome to the multi-device recording system for child collaboration research. Start here!

---

## 🎯 Quick Links By Use Case

### 👤 **I'm a Researcher/Lab Manager**

1. **First time setup**: Read [SETUP.md](SETUP.md)
2. **Before each session**: Follow [CHECKLIST.md](CHECKLIST.md)
3. **During a session**: Use [QUICKREF.md](QUICKREF.md)
4. **Questions or issues**: Refer to [README.md](README.md) troubleshooting

### 👨‍💻 **I'm a Developer/Maintaining This Code**

1. **Architecture overview**: Read [DEVELOPER.md](DEVELOPER.md)
2. **Feature details**: See [IMPLEMENTATION.md](IMPLEMENTATION.md)
3. **Modifying the code**: Check [DEVELOPER.md](DEVELOPER.md#-common-modifications)
4. **Testing**: See [DEVELOPER.md](DEVELOPER.md#-testing-checklist)

### 📊 **I Want to Understand Features**

- **What's included**: [IMPLEMENTATION.md](IMPLEMENTATION.md)
- **Technical details**: [DEVELOPER.md](DEVELOPER.md)
- **How to use each feature**: [README.md](README.md)

---

## 📖 Documentation Files

| File | Purpose | Audience | Read Time |
|------|---------|----------|-----------|
| [README.md](README.md) | Complete user guide & troubleshooting | Researchers | 20 min |
| [SETUP.md](SETUP.md) | Installation & first-run guide | New users | 10 min |
| [CHECKLIST.md](CHECKLIST.md) | Pre-session checklist & timeline | Lab staff | 5 min |
| [QUICKREF.md](QUICKREF.md) | Quick reference card (printable) | All users | 2 min |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Feature-by-feature breakdown | Developers | 15 min |
| [DEVELOPER.md](DEVELOPER.md) | Code architecture & maintenance | Developers | 20 min |
| [INDEX.md](INDEX.md) | This file | Everyone | 2 min |

---

## 🐍 Python Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| [main.py](main.py) | Interactive CLI menu | ~200 | ✅ Complete |
| [config.py](config.py) | Configuration settings | ~100 | ✅ Complete |
| [utils.py](utils.py) | Shared utilities & UI | ~400 | ✅ Complete |
| [device_checker.py](device_checker.py) | Device discovery & checks | ~350 | ✅ Complete |
| [audio_checker.py](audio_checker.py) | Dominance speaker analysis | ~300 | ✅ Complete |
| [calibration.py](calibration.py) | Camera calibration | ~250 | ✅ Complete |
| [recorder.py](recorder.py) | Main recording logic | ~400 | ✅ Complete |
| [sync_finder.py](sync_finder.py) | Post-recording sync offset | ~150 | ✅ Complete |

**Total**: ~2,150 lines of Python code

---

## 📁 Directory Structure

```
recording_system/
├── Core Python Modules
│   ├── main.py                 # Entry point
│   ├── config.py               # Settings
│   ├── utils.py                # Utilities
│   ├── device_checker.py       # Device discovery
│   ├── audio_checker.py        # Audio analysis
│   ├── calibration.py          # Camera calibration
│   ├── recorder.py             # Main recording
│   └── sync_finder.py          # Sync offset finder
│
├── Documentation
│   ├── README.md               # Main user guide
│   ├── SETUP.md                # Installation guide
│   ├── CHECKLIST.md            # Pre-session checklist
│   ├── QUICKREF.md             # Quick reference card
│   ├── IMPLEMENTATION.md       # Feature breakdown
│   ├── DEVELOPER.md            # Developer guide
│   └── INDEX.md                # This file
│
├── Configuration
│   └── requirements.txt        # Python dependencies
│
├── Runtime Directories
│   ├── outputs/                # Session recordings (auto-created)
   └── calibration/            # Camera calibration files (auto-created)
```

---

## 🚀 Getting Started

### Option 1: Quick Start (5 minutes)

```bash
# Navigate to project
cd ~/Documents/GitHub/falk_study/recording_system

# Activate virtual environment
source venv/bin/activate

# Run the system
python main.py

# Follow the menu prompts!
```

### Option 2: Full Setup (30 minutes)

1. Read [SETUP.md](SETUP.md) for complete installation
2. Install dependencies: `pip install -r requirements.txt`
3. Read [README.md](README.md) for features overview
4. Run first test: `python main.py` → Option 2 (Hardware Check)

### Option 3: Pre-Session (10 minutes)

1. Print [CHECKLIST.md](CHECKLIST.md)
2. Follow the checklist before each session
3. Keep [QUICKREF.md](QUICKREF.md) handy during recording

---

## ✨ Key Features

- ✅ **Participant-keyed assignment**: Devices assigned by color label (red, blue, green); files named `cam_{label}.mp4` / `mic_{label}.wav`
- ✅ **Paired verification panel**: Side-by-side colored preview + live VU meter per participant before recording
- ✅ **Simultaneous recording**: All webcams and lavalier mics run in parallel
- ✅ **DJI Mic 2 stereo splitting**: Two-transmitter receiver split to separate WAV files automatically
- ✅ **Hardware verification**: Pre-session checks for all devices by participant label
- ✅ **Dominant speaker analysis**: Verify mic placement per participant
- ✅ **Camera calibration**: Optional OpenCV checkerboard calibration
- ✅ **Sync beep**: Audio sync marker for post-processing alignment
- ✅ **Live recording preview**: Colored participant camera feeds while recording
- ✅ **Session logging**: JSON metadata for each recording
- ✅ **Sync finder**: Cross-correlate Insta360 with lavalier mics

---

## 🎯 Typical Workflow

```
1. SETUP (Day 1)
   └─ Install Python & dependencies (30 min)
   └─ Run device discovery (2 min)
   └─ Run hardware check (5 min)

2. PER-SESSION (5-15 min before)
   └─ Check hardware status
   └─ Verify mic placement (optional)
   └─ Position cameras & children

3. RECORDING (5-30 min)
   └─ Start Insta360 (manual)
   └─ Run Python script
   └─ Confirm checklist
   └─ Press ENTER to begin
   └─ Recording runs automatically
   └─ Press Q to stop

4. POST-RECORDING (10 min)
   └─ Backup files to external drive
   └─ Export Insta360 footage
   └─ Find sync offset (if using Insta360)
   └─ Files ready for analysis!
```

---

## 📊 Hardware Requirements

### Minimum
- macOS 10.15+ or Linux (Ubuntu 18.04+)
- Python 3.8+
- 3 USB webcams
- 3 lavalier microphones
- 4 GB RAM
- 500 MB disk space (for code + 1 session)

### Recommended
- macOS 12+ or Linux (Ubuntu 20.04+)
- Python 3.10+
- USB 3.0 hub (powered)
- 8 GB RAM
- SSD with 100 GB free space
- 10 Mbps+ internet (for optional cloud backup)

---

## 💡 Common Tasks

### I want to...

**Start recording** → Menu Option 5, or run `python main.py` → 5

**Test devices** → Menu Option 2, or run `python main.py` → 2

**Adjust camera calibration** → Menu Option 4, or run `python main.py` → 4

**Mux video + audio** → Menu Option 6

**Find sync offset** → Menu Option 7, or run `python sync_finder.py`

**Change resolution/FPS** → Edit `config.py`, lines 8–9

**Troubleshoot device issues** → See [README.md](README.md#troubleshooting)

**Understand the code** → Read [DEVELOPER.md](DEVELOPER.md)

**Print a checklist** → Use [CHECKLIST.md](CHECKLIST.md)

**Print quick reference** → Use [QUICKREF.md](QUICKREF.md)

---

## 🆘 Help & Support

### If you have questions...

| Question | Answer | Link |
|----------|--------|------|
| How do I install? | Step-by-step instructions | [SETUP.md](SETUP.md) |
| How do I use it? | Complete user guide | [README.md](README.md) |
| What should I do before each session? | Pre-session checklist | [CHECKLIST.md](CHECKLIST.md) |
| I need a quick reference | Printable card | [QUICKREF.md](QUICKREF.md) |
| What features are included? | Feature breakdown | [IMPLEMENTATION.md](IMPLEMENTATION.md) |
| How does the code work? | Architecture & code | [DEVELOPER.md](DEVELOPER.md) |

### Common Issues

| Issue | Solution | Link |
|-------|----------|------|
| Camera not detected | Restart Python, check USB | [README.md](README.md#cannot-open-camera-error) |
| Audio too quiet | Check mic powered, volume | [README.md](README.md#very-low-audio-levels) |
| Low frame rate | Reduce resolution | [README.md](README.md#low-webcam-fps) |
| Import errors | Reinstall dependencies | [SETUP.md](SETUP.md#troubleshooting-installation) |
| macOS permission denied | Grant camera access | [SETUP.md](SETUP.md#macos-grant-camera--microphone-permissions) |

---

## 🔄 Maintenance

### Updating Dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Running Tests

```bash
# Test imports
python3 -c "import cv2, sounddevice, scipy; print('OK')"

# Test device discovery
python device_checker.py

# Full system test
python main.py  # → Option 2 (Hardware Check)
```

### Checking Code

```bash
# If using pylint
pylint *.py

# If using flake8
flake8 *.py --max-line-length=100
```

---

## 📞 Contact & Support

**Questions about the system?** → See [README.md](README.md)

**Installation issues?** → See [SETUP.md](SETUP.md)

**Code questions?** → See [DEVELOPER.md](DEVELOPER.md)

**How to use before a session?** → See [CHECKLIST.md](CHECKLIST.md)

---

## 📝 License & Attribution

CMU Child Collaboration Study Lab  
April 2026  
Version 1.0

---

## 🗺️ Navigation

- **User Guides**: [README.md](README.md), [SETUP.md](SETUP.md), [CHECKLIST.md](CHECKLIST.md)
- **Quick Reference**: [QUICKREF.md](QUICKREF.md)
- **Developer Docs**: [DEVELOPER.md](DEVELOPER.md), [IMPLEMENTATION.md](IMPLEMENTATION.md)
- **Code**: [main.py](main.py), [config.py](config.py), [utils.py](utils.py), etc.

---

**Ready to start? Run: `python main.py`**

For help, see [README.md](README.md) or [SETUP.md](SETUP.md).
