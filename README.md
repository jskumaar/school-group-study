# School Group Study — Multi-Device Recording System

Recording tool for a child-collaboration study. One session records **three children at once**:

- 3 USB webcams → one video file per child
- 3 lavalier mics (DJI Mic) → one WAV file per child
- 1 Insta360 camera → started and stopped **by hand** (the software does not control it)

Each child is identified by a **color label** (default `red`, `blue`, `green`; this lab has used `yellow` instead of `green`). Files are named by label, so pairing is explicit: `cam_red.mp4` is always the camera pointed at the child whose mic is `mic_red.wav`.

> **There is no separate graphical app.** The "experimenter interface" is a **terminal menu** (run with Python) plus **OpenCV pop-up windows** for camera previews and verification. See [Experimenter interface](#experimenter-interface).

All code lives in [recording_system/](recording_system/). Deeper reference docs are in that folder (`SETUP.md`, `QUICKREF.md`, `TROUBLESHOOT.md`, `DEVELOPER.md`, …). Where they disagree with this file, this file reflects what the code actually does.

---

## Contents

1. [Hardware](#1-hardware)
2. [Software and dependencies](#2-software-and-dependencies)
3. [One-time computer setup](#3-one-time-computer-setup)
4. [Experimenter interface](#experimenter-interface)
5. [Before each session: matching camera and mic IDs](#5-before-each-session-matching-camera-and-mic-ids)
6. [Running a session: start and stop](#6-running-a-session-start-and-stop)
7. [After the session](#7-after-the-session)
8. [Output files](#8-output-files)
9. [Configuration](#9-configuration)
10. [Troubleshooting](#10-troubleshooting)
11. [Known quirks](#11-known-quirks)
12. [Data handling](#12-data-handling)

---

## 1. Hardware

| Item | Qty | Notes |
|---|---|---|
| USB webcams | 3 | Identical models are fine (the lab has used EMEET SmartCam C960). Mount so each one sees one child. |
| Powered USB 3.0 hub | 1 | Strongly recommended. Three cameras on one unpowered or USB 2.0 hub will drop frames. |
| DJI lavalier mic system | 3 transmitters | Used with a **stereo USB receiver** (two transmitters → left/right channels of one USB device) **plus** a second **wired USB receiver** for the third child. **Do not use Bluetooth for any mic** (see warning below). |

> ⚠️ **Do not use Bluetooth for the microphones.** A Bluetooth link can drop mid-session, and that child's audio can be lost for the rest of the session with no way to recover it. Bluetooth "Hands-Free" mode also records at a low telephone-quality 16 kHz. Connect every DJI receiver to the computer by USB cable, and confirm each one appears in the audio device list before the session. If you only have one stereo receiver, get a second USB receiver rather than falling back to Bluetooth.
| Insta360 camera | 1 | Operated manually. Must be able to hear the room (it records the sync beeps). |
| Speaker / computer audio output | 1 | The sync beeps play through the computer's **default output device**; the mics and the Insta360 pick them up acoustically. Volume must be audible. |
| Computer | 1 | Written for **Windows 11** (DirectShow cameras, WASAPI audio). macOS/Linux are partially supported; see [recording_system/SETUP.md](recording_system/SETUP.md). |

Disk space: budget roughly 0.5 GB per minute for three cameras plus audio. A 30-minute session is on the order of 10–15 GB.

---

## 2. Software and dependencies

| Dependency | Needed for | How to get it |
|---|---|---|
| **Python 3.8+** (3.11 has been used) | everything | python.org |
| `opencv-python` ≥ 4.8 | camera capture, previews, calibration | pip |
| `sounddevice` ≥ 0.4.6 | audio capture and sync beep | pip (bundles PortAudio on Windows/macOS) |
| `soundfile` ≥ 0.12.1 | writing WAV files | pip |
| `numpy` ≥ 1.24 | audio/video buffers | pip |
| `scipy` ≥ 1.10 | cross-correlation (sync finder) | pip |
| `rich` ≥ 13 | terminal menus and tables | pip |
| **FFmpeg** (on `PATH`) | muxing video + audio (menu option 6), extracting Insta360 audio | see below |

[recording_system/requirements.txt](recording_system/requirements.txt) also lists `pyaudio` and `ffmpeg-python`. **Nothing in the code imports either of them.** `pyaudio` can fail to install on Windows without build tools; if `pip install -r requirements.txt` fails on it, remove that line (and `ffmpeg-python`) and install the rest. The program uses the `ffmpeg` command-line binary directly.

---

## 3. One-time computer setup

### 3.1 Install Python packages

From the repository root, in PowerShell:

```powershell
cd recording_system
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..
```

(macOS/Linux: `python3 -m venv venv && source venv/bin/activate`.)

### 3.2 Install FFmpeg

- Windows: `winget install Gyan.FFmpeg` (or download from ffmpeg.org and add the `bin` folder to `PATH`)
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`

Open a **new** terminal and confirm:

```powershell
ffmpeg -version
```

If this prints a version, option 6 (mux) will work. Without FFmpeg, recording still works; only muxing is unavailable.

### 3.3 Operating-system permissions

- **Windows**: Settings → Privacy & security → **Camera** and **Microphone** → allow desktop apps to access them. In Settings → System → Sound, make sure the DJI receivers are enabled (not disabled/muted) as input devices.
- **macOS**: System Settings → Privacy & Security → Camera / Microphone → enable your terminal app.
- **Linux**: `sudo usermod -a -G audio $USER`, then log out and back in.

### 3.4 Prepare the Insta360

Charge it, make sure it has free storage, and mount it so it can see the whole group. It is controlled by hand during the session (see [section 6](#6-running-a-session-start-and-stop)).

---

## Experimenter interface

The program is started from a terminal. Run it **from the repository root** every time:

```powershell
.\recording_system\venv\Scripts\Activate.ps1
python recording_system\main.py
```

> **Always launch from the same folder.** The saved device assignments (`device_assignments.json`) are read and written relative to the folder you launch from. Launch from the repo root and you will keep reusing the file that is already there; launch from `recording_system/` and a second, separate copy is created.

You get this menu:

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

A status line under the title shows whether device assignments are loaded. After each action, press **ENTER** to return to the menu.

Camera previews appear in separate **OpenCV windows**. Those windows take **keyboard focus from the terminal**: to press a key such as `Q` or `ENTER`, click the preview window first, then press the key.

| Menu | Purpose | When to use |
|---|---|---|
| 1 | Find cameras and mics, assign them to children, verify | Every session (IDs can change), and any time hardware moves |
| 2 | 10-second camera health check (FPS) and mic level check | Every session |
| 3 | Check each mic mostly hears its own child | First time, and whenever mics are re-clipped |
| 4 | Checkerboard lens calibration | Optional; only for 3D/gaze work |
| 5 | Record | The session itself |
| 6 | Combine each `cam_X.mp4` with `mic_X.wav` | After recording |
| 7 | Compute timing offset of the Insta360 | After recording |

---

## 5. Before each session: matching camera and mic IDs

This is the step that prevents mislabelled data. Camera numbers (`0`, `1`, `2`, …) and audio device numbers are assigned by the operating system and **can change** when a USB cable is moved, a hub is re-plugged, a device is power-cycled, or the computer reboots. The saved `device_assignments.json` can therefore be stale. **Re-run option 1 at the start of every session** unless nothing has been touched since the last verified run.

### 5.1 Physical setup first

1. Plug the webcams into the **powered hub** and the hub into the computer.
2. Power on all DJI transmitters and receivers. Confirm each transmitter shows a connection to its receiver. Plug the receiver(s) into the computer.
3. Clip each lavalier mic on a child's collar. **Decide now which child wears which color** and keep it for the whole session.
4. Point each webcam at one child. Note which camera belongs to which color.

### 5.2 Run option 1 — Discover & assign devices

Choose `1`. The program then:

1. **Scans video devices** (indices 0–14) and **audio input devices**.
   - On Windows, audio devices are filtered to the WASAPI entries so each microphone appears once with its true sample rate and full name.
   - Two receivers with the same name are shown as `… (receiver 1)` / `… (receiver 2)`.
2. **Prints both device tables.** DJI devices are highlighted.
3. Offers **live previews of every camera** with its index number overlaid (answer `y`). Walk in front of each camera or cover its lens to see which index is which. Press `Q`/`ENTER` to close.
4. Asks **how many participants** (default 3) and a **label for each** (default `red`, `blue`, `green`; type `yellow` etc. to change). Labels are lower-cased.
5. For each participant asks:
   - **Camera device index** — the number from the table/preview.
   - **Mic device index** — the number from the audio table.
   - **Channel**, only if that mic device is stereo: `0` = **Left**, `1` = **Right**. A stereo DJI receiver carries two transmitters on its left and right channels. Which physical transmitter is Left vs Right depends on how they were paired, so don't guess: use the verification step below to find out.
6. Prints an **assignment summary** and the output file names it will create.

Example summary (the lab's saved configuration):

```
RED     cam → device 1  mic → device 26 ch0L  (Microphone (DJI MIC MINI))
BLUE    cam → device 2  mic → device 26 ch1R  (Microphone (DJI MIC MINI))
YELLOW  cam → device 3  mic → device 27 ch0    (Headset (DJI Mic Mini-B3549F Hands-Free))
```

Here red and blue share one stereo receiver (device 26: red is the left channel, blue the right) and yellow is a separate mono device (27). In the lab's current saved file, device 27 is a Bluetooth "Hands-Free" mic: **replace it with a wired USB receiver** (see the Bluetooth warning in section 1).

### 5.3 Verify with the paired verification panel (do not skip)

When asked **"Run paired verification panel now?"**, answer `y`. A window opens with one column per child:

- the child's **camera feed with a thick border in their color**
- a **live VU meter** for the mic assigned to them

Then, **with the children in place and wearing their mics**:

1. **Camera check** — ask the child assigned *red* to **wave**. The *red* column's video must show that child moving. Repeat for every child. If the wrong child waves in a column, the camera index is wrong.
2. **Mic check** — ask the child assigned *red* to **speak** (say their name). Only the *red* meter should jump. Repeat for each child. If the wrong meter moves, the mic index or channel is wrong. A child's meter staying flat means that mic is off, muted, unplugged, or on the wrong channel.
3. **Stereo receiver warning** — if two children on the same stereo receiver both show a level at once while only one is speaking, a banner warns of a **mono mix**: the receiver is sending the same signal on both channels. Check the DJI receiver's output/channel settings so each transmitter goes to its own channel (consult the DJI manual for your model), then re-verify before recording.

Then press (in the verification window):

- **ENTER** — everything is correct; assignments are saved to `device_assignments.json`.
- **R** — something is wrong; go back and reassign.
- **Q / ESC** — cancel and reassign.

If the pairing is wrong, redo it. **Never record without a confirmed pairing**: every analysis step assumes `cam_red` and `mic_red` belong to the same child.

### 5.4 Optional but recommended checks

- **Option 2 — hardware check.** Shows all cameras for 10 seconds and measures actual FPS (target 30 at 1280×720); then records a short level sample from each mic and reports average levels. Healthy mic levels sit around −18 to −25 dBFS while speaking; below about −35 dBFS something is wrong (muted, wrong channel, transmitter far away, low gain).
- **Option 3 — dominant speaker check.** Records 15 seconds from all mics at once while each child in turn says their name and a few sentences. The report shows, for each mic, the percentage of half-second windows where it was the loudest and the crosstalk ratio (how far above the other mics it is). Targets: dominant in **≥ 75 %** of its windows, crosstalk **≥ 10 dB**. If a mic is below 50 %, move it closer to that child's mouth. Run this the first time and any time mics are re-clipped.
- **Option 4 — camera calibration.** Hold a printed 9×6 checkerboard (25 mm squares) in front of each camera, press SPACE to capture 15+ frames, then ESC. Saved as `.npz` in `recording_system/calibration/`. Only needed for 3D pose/gaze analysis.

---

## 6. Running a session: start and stop

### 6.1 Start

1. Complete [section 5](#5-before-each-session-matching-camera-and-mic-ids) so device assignments are confirmed.
2. Make sure speaker/system volume is up (the sync beeps must be audible to the mics and Insta360) and no other app is using the cameras or mics (Zoom, Teams, browser tabs, camera apps).
3. From the main menu choose **`5`**.
4. Answer the **pre-recording checklist** (`y`/`n` each; any `n` returns you to the menu):
   - all cameras positioned and focused
   - lavalier mics clipped on and transmitters on
   - DJI receiver(s) connected and showing signal
   - Insta360 mounted and charged
   - acceptable ambient noise
5. A banner says **"INSTA360 REMINDER"**: **press record on the Insta360 now**, confirm it is recording, then press **ENTER** in the terminal.
6. The program creates `recording_system/outputs/SESSION_<YYYYMMDD_HHMMSS>/`, starts all cameras and all mic streams, waits ~0.8 s for them to initialize, then plays the **3-beep 1000 Hz sync tone** through the default speaker. Tell the group the beeps are normal.
7. A **live preview window** ("Recording — Press Q to Stop") opens: one tile per child with a colored border, label, measured FPS and frame count, plus a status tile with the elapsed clock and sample counters for each mic.

Watch the preview while recording: a tile that shows `ERROR` or a frozen image, an FPS far below 30, or a mic counter that stops increasing means that device has failed.

Any audio device that fails to open prints a red error right at the start. If that happens, stop immediately (below), fix the connection, re-run option 1, and start again — do not continue with a missing channel.

### 6.2 Stop

1. Click the preview window and press **Q** (or **ESC**). Pressing **Ctrl+C** in the terminal also stops cleanly.
2. **Wait.** The program flushes audio buffers to disk and closes the video files. Do not close the window or unplug anything until the "RECORDING COMPLETE" summary appears.
3. A banner says **"INSTA360 REMINDER: STOP recording"** — stop the Insta360 by hand.
4. The summary lists each file with frame/sample counts and size. A ❌ marks a stream that errored.
5. You are asked **"Mux cam videos with audio files now? [y/N]"**. Answer `y` if FFmpeg is installed, or do it later with option 6.
6. Press ENTER to return to the menu. Quit with `Q`.

---

## 7. After the session

### 7.1 Mux video and audio (menu option 6)

Pairs each `cam_<label>.mp4` with `mic_<label>.wav` and writes `cam_<label>_muxed.mp4` (video copied, audio encoded AAC 192 kbps). Use "last session" or enter a session folder path. The raw `cam_*.mp4` and `mic_*.wav` are kept untouched.

### 7.2 Align the Insta360 (menu option 7)

The Insta360 runs on its own clock, so its start time differs from the laptop recording. The 3-beep sync tone appears in both, which lets the program compute the offset.

1. Copy the Insta360 video off the camera.
2. Extract its audio to WAV (replace the file names):
   ```powershell
   ffmpeg -i insta360_clip.mp4 -vn -ac 1 insta360_audio.wav
   ```
3. Run menu option **7**. Enter the path to `insta360_audio.wav` and the path to any one of the session's mic WAVs (e.g. `recording_system\outputs\SESSION_…\mic_red.wav`).
4. The program cross-correlates the two and prints the offset in seconds (positive means the Insta360 started *after* the laptop recording), a correlation score, and an FFmpeg trim command. A high correlation (close to 1) means the beeps were found; a low value means the beeps were inaudible in one recording — check by eye in an audio editor.

`python recording_system\sync_finder.py` runs the same tool standalone.

---

## 8. Output files

```
recording_system/outputs/SESSION_20260427_162625/
├── cam_red.mp4        # webcam video for the red child
├── cam_blue.mp4
├── cam_yellow.mp4     # (or cam_green.mp4, depending on labels)
├── mic_red.wav        # lavalier audio for the red child
├── mic_blue.wav
├── mic_yellow.wav
├── session_log.json   # timing, device assignments, frame/sample counts, errors
└── cam_*_muxed.mp4    # only after muxing
```

`session_log.json` contains the wall-clock start time, the sync-beep time, total duration, the exact device assignments used, and per-stream frame counts, dropped frames, sample counts and errors. Check `dropped` and `error` before trusting a session.

The session folder name (`SESSION_YYYYMMDD_HHMMSS`) is also the key used to map each study group to its recording.

---

## 9. Configuration

Edit [recording_system/config.py](recording_system/config.py):

| Setting | Default | Meaning |
|---|---|---|
| `TARGET_FPS` | 30 | Webcam frame rate |
| `RESOLUTION` | (1280, 720) | Webcam resolution. Lower it (e.g. (1024, 576)) if cameras drop frames |
| `VIDEO_CODEC` | `mp4v` | FourCC for the video writer |
| `AUDIO_SAMPLERATE` | 44100 | Fallback sample rate; devices that report a native rate use that instead |
| `SYNC_TONE_ENABLED` | True | Play the beeps at session start |
| `SYNC_TONE_FREQUENCY` / `_DURATION` / `_NUM_BEEPS` / `_GAP` | 1000 Hz / 0.2 s / 3 / 0.2 s | Beep pattern |
| `VOICE_BASELINE_DURATION` | 15 s | Length of the dominant speaker check |
| `DOMINANCE_THRESHOLD_PCT` | 0.75 | Pass threshold for the dominant speaker check |
| `CROSSTALK_WARNING_DB` | 10 | Minimum separation between mics |
| `OUTPUT_BASE_DIR` | `outputs` | Folder (under `recording_system/`) where sessions are written |

---

## 10. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Option 1 finds fewer cameras than expected | Re-seat USB, use the powered hub, close other apps using the cameras, wait a few seconds after plugging in and rescan. |
| "Cannot open camera" / `ERROR` tile | Wrong or stale index, another app is using it, or Windows privacy settings block access. Re-run option 1. |
| Cameras show in the wrong column | Camera indices swapped. Reassign using the wave test. |
| Wrong child's meter moves | Wrong mic device or channel. Reassign; on a stereo receiver, swap channel 0/1. |
| Both meters move together on a stereo receiver | Receiver sending a mono mix. Check the DJI receiver's output/channel settings. |
| No DJI mics listed ("showing all audio devices") | Receiver not detected, or the device name doesn't contain "DJI". Check power/USB; look in Windows Sound settings. |
| Cannot open audio device | Device in use by another app, or Windows "exclusive mode" holding it. Close other apps, reselect in option 1. |
| Very low mic level (< −40 dBFS) | Transmitter off/muted/out of range, or wrong channel. |
| Low FPS or dropped frames | Use a powered USB 3.0 hub, lower `RESOLUTION`, close heavy apps. |
| Sync beeps missing from recordings | Speaker volume too low or wrong default output device. Raise volume; verify beeps appear in each WAV. |
| `ffmpeg not found` | Install FFmpeg and open a new terminal (see 3.2). |
| `pip install` fails on `pyaudio` | Remove `pyaudio` and `ffmpeg-python` from requirements.txt; they're unused. |
| Terminal appears frozen on exit | Press Ctrl+C; a watchdog force-exits after a few seconds. |
| Preview window ignores key presses | Click the preview window to give it focus first. |

More detail: [recording_system/TROUBLESHOOT.md](recording_system/TROUBLESHOOT.md).

---

## 11. Known quirks

- **Mic sample rates can differ per child.** Each audio device is opened at its own native rate. In the lab's configuration the stereo receiver records at 48 000 Hz and the Bluetooth headset-profile mic at **16 000 Hz**, so `mic_yellow.wav` has lower bandwidth than the other two. `session_log.json` records `audio_sr` as the 44 100 Hz config default, which does not reflect these per-device rates; check the WAV headers instead.
- **Bluetooth mics: don't.** The `Headset (… Hands-Free)` device is a Bluetooth link that can disconnect mid-session and uses a low-quality telephone profile. Use wired USB receivers for all three children.
- **Video codec.** `VIDEO_CODEC = 'mp4v'` is MPEG-4 Part 2, not H.264, despite the comment in `config.py`. Files play normally but are larger than H.264.
- **Camera names are generic** (`Camera 0`, `Camera 1`, …) because OpenCV does not expose device names. Always identify cameras visually, never by name.
- **The Insta360 is not controlled by software.** Forgetting to start it before pressing ENTER, or to stop it afterward, is the most common operator error.
- Some of the older docs in `recording_system/` mention only `green` as the third color and describe a macOS-first setup.

---

## 12. Data handling

Session folders contain **video and audio of children**. They are written to `recording_system/outputs/`, which is excluded by `.gitignore` so it can't be committed by accident. Don't force-add it. Store and share recordings only under the study's IRB-approved data-management plan, and never commit raw recordings to GitHub.
