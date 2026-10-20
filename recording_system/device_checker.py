"""
Device discovery, participant assignment, and pre-session hardware verification.

Assignment structure (device_assignments.json):
{
  "participants": [
    {"label": "red",   "cam_device": 2, "mic_device": 3, "mic_channel": 0,
     "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
    {"label": "blue",  "cam_device": 0, "mic_device": 3, "mic_channel": 1,
     "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
    {"label": "green", "cam_device": 1, "mic_device": 5, "mic_channel": 0,
     "mic_name": "DJI Mic BT", "channels_on_device": 1}
  ],
  "audio_devices": [
    {"device": 3, "name": "DJI Mic 2 (Receiver)", "channels": 2,
     "labels": ["mic_red", "mic_blue"], "samplerate": 44100, "is_stereo_pair": true},
    {"device": 5, "name": "DJI Mic BT", "channels": 1,
     "labels": ["mic_green"], "samplerate": 44100, "is_stereo_pair": false}
  ]
}

Output files are named by participant:
  cam_red.mp4 + mic_red.wav,  cam_blue.mp4 + mic_blue.wav,  cam_green.mp4 + mic_green.wav
"""

import os
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import sounddevice as sd
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

import config
from utils import (
    print_section, print_ok, print_warning, print_error, print_info,
    print_video_devices_table, print_audio_devices_table, print_device_check_summary,
    print_reminder, get_vu_meter, compute_rms_db, compute_peak_db,
    is_dji_mic_device, filter_dji_mic_devices,
    open_video_capture,
)

console = Console()

# ─── PARTICIPANT COLOR PALETTE (BGR for OpenCV) ───────────────────────────────

_LABEL_COLORS_BGR: Dict[str, Tuple[int, int, int]] = {
    "red":    (0,   0,   220),
    "blue":   (220, 80,  0  ),
    "green":  (0,   180, 0  ),
    "yellow": (0,   210, 230),
    "purple": (200, 0,   180),
    "orange": (0,   130, 255),
    "pink":   (180, 100, 220),
    "teal":   (180, 200, 0  ),
    "white":  (220, 220, 220),
}
_DEFAULT_LABELS = ["red", "blue", "green"]


def _label_color(label: str) -> Tuple[int, int, int]:
    return _LABEL_COLORS_BGR.get(label.lower(), (160, 160, 160))


# ─── DEVICE DISCOVERY ─────────────────────────────────────────────────────────

def _probe_camera(idx: int, result: dict):
    try:
        cap = open_video_capture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                result.update({
                    "available": True, "width": w, "height": h,
                    "fps": cap.get(cv2.CAP_PROP_FPS) or 30.0,
                    "name": f"Camera {idx}",
                })
            cap.release()
    except Exception:
        pass


def discover_video_devices(max_index: int = 15) -> List[Dict]:
    """Probe video device indices 0–max_index with a timeout each."""
    results = [
        {"index": i, "available": False, "name": f"Camera {i}", "width": 0, "height": 0, "fps": 0}
        for i in range(max_index)
    ]
    threads = [threading.Thread(target=_probe_camera, args=(i, results[i]), daemon=True) for i in range(max_index)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8.0)
    return [r for r in results if r["available"]]


def discover_audio_devices() -> List[Dict]:
    """
    Return audio input devices via sounddevice.

    On Windows, PortAudio exposes every physical device multiple times — once
    per host API (MME, DirectSound, WASAPI, WDM-KS). This produces 3-4 duplicate
    entries per microphone with identical names but different sample rates.

    When WASAPI is available we keep only those entries: WASAPI gives one entry
    per physical device, uses the device's native sample rate, and provides full
    (untruncated) device names. Devices with no WASAPI entry are included as-is.
    """
    try:
        host_apis = {i: api["name"] for i, api in enumerate(sd.query_hostapis())}
    except Exception:
        host_apis = {}

    all_devs = [
        {
            "index": i,
            "name": d["name"],
            "available": True,
            "channels": d["max_input_channels"],
            "samplerate": int(d["default_samplerate"]),
            "hostapi": d["hostapi"],
            "hostapi_name": host_apis.get(d["hostapi"], ""),
        }
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]

    if sys.platform != "win32":
        for dev in all_devs:
            dev["display_name"] = dev["name"]
        return all_devs

    wasapi_id = next(
        (i for i, name in host_apis.items() if "WASAPI" in name), None
    )
    if wasapi_id is None:
        for dev in all_devs:
            dev["display_name"] = dev["name"]
        return all_devs

    # Group by device name; for each name keep WASAPI entries if any exist
    by_name: Dict[str, List[Dict]] = {}
    for dev in all_devs:
        by_name.setdefault(dev["name"], []).append(dev)

    result = []
    for devs in by_name.values():
        wasapi = [d for d in devs if d["hostapi"] == wasapi_id]
        result.extend(wasapi if wasapi else devs)

    result.sort(key=lambda d: d["index"])

    # Remove MME/DirectSound entries whose name is a 31-char truncated prefix of a
    # WASAPI entry's name. Windows MME truncates device names at MAXPNAMELEN-1 = 31
    # characters, producing duplicate entries with the wrong sample rate (the MME
    # entry reports Windows' default rate, not the device's native rate). Example:
    #   MME:   "Headset (DJI Mic Mini-B3549F Ha"  44100 Hz  ← drop
    #   WASAPI:"Headset (DJI Mic Mini-B3549F Hands-Free)"  16000 Hz  ← keep
    wasapi_names = {d["name"] for d in result if d["hostapi"] == wasapi_id}
    result = [
        d for d in result
        if d["hostapi"] == wasapi_id
        or len(d["name"]) != 31
        or not any(wn.startswith(d["name"]) and wn != d["name"] for wn in wasapi_names)
    ]

    # Add display_name: identical-name devices get a "(receiver N)" suffix so the
    # researcher can distinguish two physical DJI receivers of the same model.
    name_counts: Dict[str, int] = {}
    for dev in result:
        name_counts[dev["name"]] = name_counts.get(dev["name"], 0) + 1
    name_seen: Dict[str, int] = {}
    for dev in result:
        n = dev["name"]
        if name_counts[n] > 1:
            name_seen[n] = name_seen.get(n, 0) + 1
            dev["display_name"] = f"{n} (receiver {name_seen[n]})"
        else:
            dev["display_name"] = n

    return result


# ─── WEBCAM CHECK THREAD ──────────────────────────────────────────────────────

class WebcamCheckThread(threading.Thread):
    """Captures frames from one webcam; exposes latest frame for preview/verification."""

    def __init__(self, device_index: int, duration: float = 10.0):
        super().__init__(daemon=True)
        self.device_index = device_index
        self.duration = duration
        self.stop_event = threading.Event()
        self.frame_count = 0
        self.dropped = 0
        self.resolution: Tuple[int, int] = (0, 0)
        self.error: Optional[str] = None
        self._latest: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            cap = open_video_capture(self.device_index)
            if not cap.isOpened():
                self.error = f"Cannot open device {self.device_index}"
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.RESOLUTION[1])
            cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)
            self.resolution = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            end = time.time() + self.duration
            while time.time() < end and not self.stop_event.is_set():
                ret, frame = cap.read()
                if ret:
                    self.frame_count += 1
                    with self._lock:
                        self._latest = cv2.resize(frame, (320, 240))
                else:
                    self.dropped += 1
            cap.release()
        except Exception as e:
            self.error = str(e)

    @property
    def actual_fps(self) -> float:
        return self.frame_count / self.duration if self.duration > 0 else 0.0

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "warning" if self.actual_fps < config.TARGET_FPS * 0.7 else "ok"


# ─── CAMERA SELECTION PREVIEW ─────────────────────────────────────────────────

def _show_all_cameras_grid(video_devices: List[Dict], warmup_seconds: float = 2.0):
    """
    Show all cameras simultaneously with their index numbers overlaid.
    Runs until the researcher presses Q or ENTER — no fixed timeout.
    A warmup delay lets CAP_DSHOW cameras produce their first frame before display.
    """
    if not video_devices:
        return

    threads = {}
    for dev in video_devices:
        t = WebcamCheckThread(dev["index"], duration=300)  # stopped via stop_event
        t.start()
        threads[dev["index"]] = t

    print_info(f"Camera preview opening — giving cameras {warmup_seconds:.0f}s to initialise…")
    time.sleep(warmup_seconds)

    cell_w, cell_h = 320, 240
    print_info("Note the [index] number in each frame. Press Q or ENTER in the window when done.")

    _kill_timer = None
    try:
        while True:
            cells = []
            for dev in video_devices:
                frame = threads[dev["index"]].get_frame()
                if frame is not None:
                    cell = frame.copy()
                else:
                    cell = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
                    cv2.putText(cell, "Initialising...", (10, cell_h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1)
                cv2.rectangle(cell, (0, 0), (cell_w - 1, cell_h - 1), (60, 60, 60), 2)
                cv2.putText(cell, f"[{dev['index']}]", (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 255), 2)
                cells.append(cell)

            if not cells:
                break

            cols = min(3, len(cells))
            while len(cells) % cols:
                cells.append(np.zeros((cell_h, cell_w, 3), dtype=np.uint8))

            rows = [np.hstack(cells[i:i + cols]) for i in range(0, len(cells), cols)]
            cv2.imshow("All Cameras — note index numbers, press Q/ENTER to close", np.vstack(rows))

            if cv2.waitKey(33) & 0xFF in (ord("q"), ord("Q"), 13, 27):
                break
    except KeyboardInterrupt:
        # Arm kill timer before cleanup — if destroyAllWindows stalls on Windows,
        # os._exit fires after 3 s so the terminal is never permanently frozen.
        _kill_timer = threading.Timer(3.0, os._exit, args=(1,))
        _kill_timer.daemon = True
        _kill_timer.start()
        raise
    finally:
        cv2.destroyAllWindows()
        for t in threads.values():
            t.stop()
        if _kill_timer is not None:
            _kill_timer.cancel()


# ─── PARTICIPANT ASSIGNMENT ───────────────────────────────────────────────────

def assign_participants_interactive(
    video_devices: List[Dict], audio_devices: List[Dict]
) -> Dict:
    """
    Assign cameras and mics to named participants (e.g. red/blue/green).

    For each participant the researcher picks:
      - Which camera device index shows that child
      - Which DJI mic device + channel belongs to that child

    Builds the participant-keyed assignment dict and runs the paired
    verification panel (Option 3) before returning.
    """
    print_section("PARTICIPANT-KEYED DEVICE ASSIGNMENT")

    # Show device tables
    console.print("\n[bold cyan]AVAILABLE VIDEO DEVICES[/bold cyan]")
    print_video_devices_table(video_devices)
    console.print("\n[bold cyan]AVAILABLE AUDIO DEVICES[/bold cyan]")
    print_audio_devices_table(audio_devices, highlight_dji=True)

    # Offer camera preview grid to help researcher identify indices
    if video_devices:
        show_prev = Prompt.ask("Show live camera previews to identify device indices?", choices=["y", "n"], default="y")
        if show_prev.lower() == "y":
            _show_all_cameras_grid(video_devices)

    # Participant labels
    n = int(Prompt.ask("Number of participants", default="3"))
    n = max(1, min(6, n))

    labels = []
    for i in range(n):
        default = _DEFAULT_LABELS[i] if i < len(_DEFAULT_LABELS) else f"child{i + 1}"
        lbl = Prompt.ask(f"  Label for participant {i + 1} (e.g. color or name)", default=default).strip().lower()
        labels.append(lbl)

    # DJI mic devices (fall back to all if none found)
    dji_mics = filter_dji_mic_devices(audio_devices)
    if not dji_mics:
        print_warning("No DJI Mic devices found. Showing all audio devices.")
        dji_mics = audio_devices

    assigned_cam_devices: set = set()
    assigned_mic_channels: Dict[int, set] = {}  # device_idx → set of taken channels
    participants: List[Dict] = []

    for label in labels:
        color = _label_color(label)
        console.print(f"\n[bold]── Assigning participant: [/bold]", end="")
        console.print(f"[bold]● {label.upper()}[/bold]", style=f"rgb({color[2]},{color[1]},{color[0]})")

        # ── Camera ──────────────────────────────────────────────────────────
        cam_table = Table(show_header=True, header_style="cyan", show_lines=False)
        cam_table.add_column("Idx", width=5)
        cam_table.add_column("Name")
        cam_table.add_column("", width=8)
        for d in video_devices:
            taken_by = next((p["label"].upper() for p in participants if p["cam_device"] == d["index"]), "")
            cam_table.add_row(str(d["index"]), d["name"], f"[yellow]{taken_by}[/yellow]" if taken_by else "")
        console.print(cam_table)

        while True:
            val = Prompt.ask(f"  Camera device index for [{label.upper()}]")
            try:
                cam_idx = int(val)
                if not any(d["index"] == cam_idx for d in video_devices):
                    print_error("Index not in device list")
                    continue
                if cam_idx in assigned_cam_devices:
                    ov = Prompt.ask("  Already assigned to another participant — override?", choices=["y", "n"], default="n")
                    if ov.lower() != "y":
                        continue
                assigned_cam_devices.add(cam_idx)
                break
            except ValueError:
                print_error("Enter a number")

        # ── Mic ──────────────────────────────────────────────────────────────
        console.print(f"\n  [bold]DJI mic for [{label.upper()}][/bold]")
        print_audio_devices_table(dji_mics, highlight_dji=False)

        while True:
            val = Prompt.ask(f"  Mic device index for [{label.upper()}]")
            try:
                mic_idx = int(val)
                mic_dev = next((d for d in audio_devices if d["index"] == mic_idx), None)
                if not mic_dev:
                    print_error("Index not found in audio device list")
                    continue
                break
            except ValueError:
                print_error("Enter a number")

        # ── Channel (for stereo DJI receivers) ───────────────────────────────
        mic_channel = 0
        if mic_dev["channels"] >= 2:
            taken_chs = assigned_mic_channels.get(mic_idx, set())
            avail = [ch for ch in range(mic_dev["channels"]) if ch not in taken_chs]

            if not avail:
                print_warning("All channels on this device taken — defaulting to channel 0")
                mic_channel = 0
            elif len(avail) == 1:
                mic_channel = avail[0]
                ch_name = "Left" if mic_channel == 0 else "Right"
                print_info(f"  Only channel {mic_channel} ({ch_name}) available on this device")
            else:
                ch_names = {0: "Left", 1: "Right"}
                ch_opts = [str(c) for c in avail]
                ch_desc = "  /  ".join(f"{c} = {ch_names.get(c, str(c))}" for c in avail)
                mic_channel = int(Prompt.ask(f"  Channel ({ch_desc})", choices=ch_opts, default=ch_opts[0]))

        assigned_mic_channels.setdefault(mic_idx, set()).add(mic_channel)

        ch_name = "Left" if (mic_dev["channels"] >= 2 and mic_channel == 0) else \
                  "Right" if (mic_dev["channels"] >= 2 and mic_channel == 1) else "mono"
        mic_display = mic_dev.get("display_name", mic_dev["name"])
        print_ok(f"  {label.upper()}: cam=device {cam_idx},  mic=device {mic_idx} ch{mic_channel} ({ch_name})  [{mic_display[:32]}]")

        participants.append({
            "label": label,
            "cam_device": cam_idx,
            "mic_device": mic_idx,
            "mic_channel": mic_channel,
            "mic_name": mic_display,   # display_name so VU meter identifies the receiver
            "channels_on_device": mic_dev["channels"],
        })

    # ── Build audio_devices list ──────────────────────────────────────────────
    # Group participants by device; sort each group by channel so labels[ch] is correct
    dev_map: Dict[int, List[Tuple[int, str]]] = {}
    for p in participants:
        dev_map.setdefault(p["mic_device"], []).append((p["mic_channel"], p["label"]))

    audio_devices_list = []
    for dev_idx, ch_label_pairs in dev_map.items():
        ch_label_pairs.sort(key=lambda x: x[0])
        dev_info = next(d for d in audio_devices if d["index"] == dev_idx)
        max_ch = max(ch for ch, _ in ch_label_pairs) + 1
        audio_devices_list.append({
            "device": dev_idx,
            "name": dev_info["name"],
            "channels": max_ch,
            "labels": [f"mic_{lbl}" for _, lbl in ch_label_pairs],
            "samplerate": dev_info["samplerate"],
            "is_stereo_pair": max_ch >= 2,
        })

    assignments = {"participants": participants, "audio_devices": audio_devices_list}

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print("\n[bold green]Assignment Summary[/bold green]")
    for p in participants:
        ch_lbl = "L" if (p["channels_on_device"] >= 2 and p["mic_channel"] == 0) else \
                 "R" if (p["channels_on_device"] >= 2 and p["mic_channel"] == 1) else ""
        console.print(
            f"  [bold]{p['label'].upper():8s}[/bold]  "
            f"cam → device {p['cam_device']}  "
            f"mic → device {p['mic_device']} ch{p['mic_channel']}{ch_lbl}  "
            f"({p['mic_name'][:26]})"
        )
    console.print("\n[bold cyan]Output files per participant:[/bold cyan]")
    for p in participants:
        console.print(f"  cam_{p['label']}.mp4   +   mic_{p['label']}.wav")

    # ── Run paired verification (Option 3) ────────────────────────────────────
    run_v = Prompt.ask("\nRun paired verification panel now?", choices=["y", "n"], default="y")
    if run_v.lower() == "y":
        confirmed = run_paired_verification(participants, audio_devices_list)
        if not confirmed:
            print_warning("Returning to reassign…")
            return assign_participants_interactive(video_devices, audio_devices)

    return assignments


# ─── PAIRED VERIFICATION PANEL (OPTION 3) ────────────────────────────────────

def _build_verification_grid(
    participants: List[Dict],
    frames: Dict[str, Optional[np.ndarray]],
    audio_levels: Dict[str, float],
    mono_mix_warning: bool = False,
) -> np.ndarray:
    """
    Build a side-by-side verification display — one column per participant.
    Each column: colored label banner / camera preview with colored border / live VU meter.
    Footer shows keyboard instructions.
    """
    n = len(participants)
    cell_w   = 320
    label_h  = 32
    cam_h    = 240
    vu_h     = 110
    footer_h = 72 if mono_mix_warning else 38
    total_h  = label_h + cam_h + vu_h + footer_h
    total_w  = cell_w * n

    grid = np.zeros((total_h, total_w, 3), dtype=np.uint8)

    for col, p in enumerate(participants):
        x     = col * cell_w
        color = _label_color(p["label"])

        # ── Label banner ──────────────────────────────────────────────────────
        banner = np.full((label_h, cell_w, 3), [c // 4 for c in color], dtype=np.uint8)
        cv2.putText(banner, f"  {p['label'].upper()}", (6, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)
        grid[:label_h, x:x + cell_w] = banner

        # ── Camera preview ────────────────────────────────────────────────────
        y_cam = label_h
        frame = frames.get(p["label"])
        if frame is not None:
            cell = cv2.resize(frame, (cell_w, cam_h))
        else:
            cell = np.zeros((cam_h, cell_w, 3), dtype=np.uint8)
            cv2.putText(cell, f"cam device {p['cam_device']}", (70, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (70, 70, 70), 1)
            cv2.putText(cell, "No signal", (110, 145),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 1)

        cv2.rectangle(cell, (0, 0), (cell_w - 1, cam_h - 1), color, 5)
        cv2.putText(cell, f"cam_device={p['cam_device']}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
        grid[y_cam:y_cam + cam_h, x:x + cell_w] = cell

        # ── VU meter panel ────────────────────────────────────────────────────
        y_vu = label_h + cam_h
        vu   = np.zeros((vu_h, cell_w, 3), dtype=np.uint8)

        db       = audio_levels.get(p["label"], -96.0)
        ch_idx   = p.get("mic_channel", 0)
        n_ch     = p.get("channels_on_device", 1)
        ch_label = "Left" if (n_ch >= 2 and ch_idx == 0) else \
                   "Right" if (n_ch >= 2 and ch_idx == 1) else "mono"

        cv2.putText(vu, p.get("mic_name", "")[:26], (6, 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1)
        cv2.putText(vu, f"device {p['mic_device']}  ch{ch_idx} ({ch_label})", (6, 33),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, (110, 110, 110), 1)

        bar_max  = cell_w - 20
        bar_fill = int((max(-60.0, min(0.0, db)) + 60.0) / 60.0 * bar_max)
        cv2.rectangle(vu, (10, 43), (10 + bar_fill, 68), color, -1)
        cv2.rectangle(vu, (10, 43), (10 + bar_max, 68), (50, 50, 50), 1)

        db_color = (0, 220, 0) if db > -40 else (0, 165, 255) if db > -55 else (80, 80, 80)
        sig_txt  = "SIGNAL OK" if db > -40 else "LOW" if db > -55 else "SILENT"
        cv2.putText(vu, f"{db:.1f} dBFS  {sig_txt}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, db_color, 1)

        grid[y_vu:y_vu + vu_h, x:x + cell_w] = vu

        # Column separator
        if col < n - 1:
            cv2.line(grid, (x + cell_w - 1, 0), (x + cell_w - 1, total_h - footer_h), (50, 50, 50), 1)

    # ── Footer ────────────────────────────────────────────────────────────────
    y_f    = label_h + cam_h + vu_h
    footer = np.zeros((footer_h, total_w, 3), dtype=np.uint8)
    cv2.putText(footer, "ENTER = confirm all pairings", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 230, 230), 1)
    cv2.putText(footer, "R = return to reassign", (10, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (160, 160, 160), 1)
    if mono_mix_warning:
        cv2.rectangle(footer, (0, 42), (total_w - 1, footer_h - 1), (0, 0, 80), -1)
        cv2.putText(footer, "WARNING: both channels active at once!", (10, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 100, 255), 1)
        cv2.putText(footer, "Receiver may be in MONO/MIX mode -- switch to Dual/Stereo output on the receiver",
                    (10, footer_h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 80, 220), 1)
    grid[y_f:, :] = footer

    return grid


def run_paired_verification(
    participants: List[Dict], audio_devices: List[Dict]
) -> bool:
    """
    Show each participant's camera preview side-by-side with their mic VU meter.

    The researcher asks each child to wave (confirms camera assignment) and
    speak (confirms mic assignment). The colored border on each camera preview
    matches the participant's label color, making mis-pairings immediately obvious.

    Returns True (confirmed) or False (researcher wants to reassign).
    """
    print_section("PAIRED VERIFICATION PANEL")
    print_info("Ask each child to wave → confirm camera | speak → confirm mic")
    print_info("ENTER to confirm all pairings   |   R to return and reassign")

    # Start camera threads
    cam_threads: Dict[str, WebcamCheckThread] = {}
    for p in participants:
        t = WebcamCheckThread(p["cam_device"], duration=300)  # long; stopped manually
        t.start()
        cam_threads[p["label"]] = t

    # Per-participant audio level (updated by InputStream callbacks)
    audio_levels: Dict[str, float] = {p["label"]: -96.0 for p in participants}
    audio_streams = []

    # Open one stream per unique audio device
    device_groups: Dict[int, List[Dict]] = {}
    for p in participants:
        device_groups.setdefault(p["mic_device"], []).append(p)

    for dev_idx, dev_parts in device_groups.items():
        max_ch = max(p["mic_channel"] for p in dev_parts) + 1

        def _make_cb(dp):
            def _cb(indata, frames, t, status):
                for pp in dp:
                    ch = min(pp["mic_channel"], indata.shape[1] - 1) if indata.ndim > 1 else 0
                    samples = indata[:, ch] if indata.ndim > 1 else indata.flatten()
                    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
                    audio_levels[pp["label"]] = 20.0 * float(np.log10(rms + 1e-10))
            return _cb

        try:
            # Use the device's native sample rate from audio_devices; WASAPI entries
            # on Windows report 48000 and will error if opened at a different rate.
            dev_info = next((d for d in audio_devices if d["device"] == dev_idx), None)
            native_sr = dev_info["samplerate"] if dev_info else 44100
            stream = sd.InputStream(
                device=dev_idx, channels=max_ch, samplerate=native_sr,
                dtype="float32", blocksize=1024,
                callback=_make_cb(dev_parts),
            )
            stream.start()
            audio_streams.append(stream)
        except Exception as e:
            print_error(f"Cannot open audio device {dev_idx} for verification: {e}")

    # Build a device→participants map for mono-mix detection
    _stereo_device_groups: Dict[int, List[Dict]] = {}
    for p in participants:
        if p.get("channels_on_device", 1) >= 2:
            _stereo_device_groups.setdefault(p["mic_device"], []).append(p)

    _kill_timer = None
    confirmed = False
    try:
        while True:
            frames = {p["label"]: cam_threads[p["label"]].get_frame() for p in participants}

            # Mono-mix detection: if 2+ participants on the same stereo device are
            # simultaneously above -40 dBFS, both channels carry the same signal.
            mono_mix_warning = False
            for dev_parts in _stereo_device_groups.values():
                if len(dev_parts) >= 2:
                    active = sum(1 for p in dev_parts if audio_levels.get(p["label"], -96.0) > -40.0)
                    if active >= 2:
                        mono_mix_warning = True
                        break

            grid   = _build_verification_grid(participants, frames, audio_levels, mono_mix_warning)
            cv2.imshow("Paired Verification — ENTER confirm | R reassign", grid)
            key = cv2.waitKey(33) & 0xFF
            if key in (13, ord("\r"), ord("\n")):   # ENTER
                confirmed = True
                break
            elif key in (ord("r"), ord("R")):
                confirmed = False
                break
            elif key in (ord("q"), ord("Q"), 27):   # Q / ESC
                confirmed = False
                break
    except KeyboardInterrupt:
        confirmed = False
        # Arm kill timer before the finally block runs — if destroyAllWindows or
        # Pa_CloseStream stalls on Windows WASAPI, os._exit fires in 3 s so the
        # terminal is never permanently frozen.
        _kill_timer = threading.Timer(3.0, os._exit, args=(1,))
        _kill_timer.daemon = True
        _kill_timer.start()
        raise
    finally:
        cv2.destroyAllWindows()
        for t in cam_threads.values():
            t.stop()
        for s in audio_streams:
            try:
                # abort() (Pa_AbortStream) returns immediately.
                # close() (Pa_CloseStream) can stall on WASAPI even after abort, so
                # we skip it here; the stream is released when the object is GC'd.
                s.abort()
            except Exception:
                pass
        if _kill_timer is not None:
            _kill_timer.cancel()

    if confirmed:
        print_ok("Pairings confirmed!")
    else:
        print_warning("Pairings not confirmed — returning to reassignment")

    return confirmed


# ─── PRE-SESSION HARDWARE CHECK ───────────────────────────────────────────────

def _build_hw_check_grid(
    participants: List[Dict],
    cam_threads: Dict[str, "WebcamCheckThread"],
) -> np.ndarray:
    """2×N grid (or 1×N if ≤3 participants) showing camera health during HW check."""
    cell_w, cell_h = 320, 240
    cells = []
    for p in participants:
        t = cam_threads.get(p["label"])
        if t is None:
            cell = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
            cv2.putText(cell, f"{p['label'].upper()} N/A", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)
        else:
            frame = t.get_frame()
            cell  = frame if frame is not None else np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
            color = (0, 0, 200) if t.error else (0, 165, 255) if t.status == "warning" else (0, 200, 0)
            cv2.putText(cell, f"{p['label'].upper()}  {t.actual_fps:.0f}fps",
                        (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
            cv2.rectangle(cell, (0, 0), (cell_w - 1, cell_h - 1), _label_color(p["label"]), 3)
        cells.append(cell)

    # Pad to even number of cells
    if len(cells) % 2 and len(cells) > 1:
        cells.append(np.zeros((cell_h, cell_w, 3), dtype=np.uint8))

    if len(cells) <= 3:
        return np.hstack(cells) if cells else np.zeros((cell_h, cell_w, 3), dtype=np.uint8)

    mid = len(cells) // 2
    return np.vstack([np.hstack(cells[:mid]), np.hstack(cells[mid:])])


def run_hardware_check(assignments: Dict) -> Dict:
    """
    Check all assigned cameras and mics simultaneously.
    Cameras: 10-second live preview with FPS measurement.
    Mics: 5-second simultaneous level check.
    Offers the paired verification panel at the end.
    """
    print_section("PRE-SESSION HARDWARE CHECK")
    results: Dict = {"cameras": {}, "mics": {}}

    participants = assignments.get("participants", [])

    # ── Camera check ──────────────────────────────────────────────────────────
    if not participants:
        print_warning("No participant assignments found — skipping camera check")
    else:
        console.print(f"\n[bold cyan]Checking {len(participants)} cameras (10 seconds)…[/bold cyan]")
        cam_threads: Dict[str, WebcamCheckThread] = {}
        for p in participants:
            t = WebcamCheckThread(p["cam_device"], duration=10.0)
            t.start()
            cam_threads[p["label"]] = t

        _hw_kill = None
        try:
            end_t = time.time() + 10.5
            while time.time() < end_t:
                grid = _build_hw_check_grid(participants, cam_threads)
                cv2.imshow("Camera Check — press Q to skip", grid)
                if cv2.waitKey(33) & 0xFF == ord("q"):
                    break
        except KeyboardInterrupt:
            _hw_kill = threading.Timer(3.0, os._exit, args=(1,))
            _hw_kill.daemon = True
            _hw_kill.start()
            raise
        finally:
            cv2.destroyAllWindows()
            for t in cam_threads.values():
                t.stop()
                t.join(timeout=1.0)
            if _hw_kill is not None:
                _hw_kill.cancel()

        for p in participants:
            t   = cam_threads[p["label"]]
            key = p["label"]
            if t.error:
                results["cameras"][key] = {"status": "error", "error": t.error, "fps": 0.0, "resolution": "?"}
            elif t.status == "warning":
                results["cameras"][key] = {
                    "status": "warning", "fps": t.actual_fps,
                    "resolution": f"{t.resolution[0]}x{t.resolution[1]}",
                    "warning": f"Low FPS ({t.actual_fps:.1f} vs target {config.TARGET_FPS})",
                }
            else:
                results["cameras"][key] = {
                    "status": "ok", "fps": t.actual_fps,
                    "resolution": f"{t.resolution[0]}x{t.resolution[1]}",
                }

    # ── Mic check ─────────────────────────────────────────────────────────────
    audio_devs = assignments.get("audio_devices", [])
    if not audio_devs:
        print_warning("No audio devices assigned — skipping mic check")
    else:
        console.print(f"\n[bold cyan]Checking {len(audio_devs)} audio device(s) (5 seconds)…[/bold cyan]")
        console.print("[dim]Make some noise near the mics now…[/dim]\n")

        mic_results: Dict[str, dict] = {}
        mic_threads = []

        for adev in audio_devs:
            r: dict = {"level_db": -96.0, "peak_db": -96.0, "done": False, "error": None}
            for label in adev["labels"]:
                mic_results[label] = r  # labels on same device share a result

            def _check(dev_idx, ch, sr, duration, out):
                try:
                    rec = sd.rec(int(duration * sr), samplerate=sr, channels=ch,
                                 device=dev_idx, dtype="float32")
                    sd.wait()
                    mono = rec.mean(axis=1) if rec.ndim > 1 else rec.flatten()
                    int16 = (mono * 32767).astype(np.int16)
                    out["level_db"] = compute_rms_db(int16, ref=32768)
                    out["peak_db"]  = compute_peak_db(int16, ref=32768)
                    out["done"] = True
                except Exception as e:
                    out["error"] = str(e)
                    out["done"] = True

            t = threading.Thread(
                target=_check,
                args=(adev["device"], adev["channels"], adev.get("samplerate", config.AUDIO_SAMPLERATE), 5.0, r),
                daemon=True,
            )
            mic_threads.append((adev, r, t))
            t.start()

        start = time.time()
        while time.time() - start < 5.5:
            time.sleep(0.4)
            for adev, r, _ in mic_threads:
                db = r.get("level_db", -96.0)
                for label in adev["labels"]:
                    console.print(f"  [cyan]{label}[/cyan]  {get_vu_meter(db)}")

        for _, _, t in mic_threads:
            t.join(timeout=3.0)

        for adev, r, _ in mic_threads:
            db  = r.get("level_db", -96.0)
            pk  = r.get("peak_db",  -96.0)
            err = r.get("error")
            for label in adev["labels"]:
                if err:
                    results["mics"][label] = {"status": "error", "error": err}
                elif db < -40:
                    results["mics"][label] = {"status": "warning", "level_db": db, "peak_db": pk,
                                               "warning": "Very low level — check connection or placement"}
                elif pk > -3:
                    results["mics"][label] = {"status": "warning", "level_db": db, "peak_db": pk,
                                               "warning": "Clipping — mic too close or gain too high"}
                else:
                    results["mics"][label] = {"status": "ok", "level_db": db, "peak_db": pk}

    # ── Insta360 reminder ─────────────────────────────────────────────────────
    print_reminder("INSTA360", "Insta360 is controlled manually. Start it before pressing ENTER to record.")

    print_device_check_summary(results)

    # ── Offer verification re-run ─────────────────────────────────────────────
    if participants:
        recheck = Prompt.ask("\nRun paired verification panel to re-confirm pairings?", choices=["y", "n"], default="n")
        if recheck.lower() == "y":
            run_paired_verification(participants, assignments.get("audio_devices", []))

    return results


if __name__ == "__main__":
    print_section("Quick discovery test")
    vd = discover_video_devices()
    ad = discover_audio_devices()
    print_ok(f"{len(vd)} video, {len(ad)} audio")
    assignments = assign_participants_interactive(vd, ad)
    run_hardware_check(assignments)