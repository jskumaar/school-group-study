"""
Utility functions: UI formatting, audio processing, file helpers, post-processing.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2

import numpy as np
from scipy import signal
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


# ─── PARTICIPANT COLOR PALETTE (BGR for OpenCV) ───────────────────────────────

LABEL_COLORS_BGR: Dict[str, tuple] = {
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


def label_color_bgr(label: str) -> tuple:
    return LABEL_COLORS_BGR.get(label.lower(), (160, 160, 160))


# ─── VIDEO CAPTURE HELPER ─────────────────────────────────────────────────────

def open_video_capture(device_index: int) -> cv2.VideoCapture:
    """
    Open a VideoCapture with the most reliable backend for the current platform.

    On Windows, DirectShow (CAP_DSHOW) is tried first because MSMF (the default)
    often fails to enumerate multiple identical USB cameras (e.g. three EMEET
    SmartCam C960 units all appearing as 'Camera 0'). CAP_DSHOW gives each
    camera a stable sequential index.

    Falls back to the platform default if CAP_DSHOW fails to open.
    """
    if sys.platform == "win32":
        cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
        cap.release()
    return cv2.VideoCapture(device_index)


# ─── DJI MIC FILTERING ───────────────────────────────────────────────────────

def is_dji_mic_device(device_name: str) -> bool:
    """
    Return True only for DJI Mic devices.
    Requires 'dji' in the device name (case-insensitive).
    This avoids false-matching built-in mics that contain 'Microphone'.
    """
    return "dji" in device_name.lower()


def filter_dji_mic_devices(audio_devices: List[Dict]) -> List[Dict]:
    """Return confirmed DJI Mic devices (matched by name)."""
    return [d for d in audio_devices if d.get("available") and is_dji_mic_device(d.get("name", ""))]


def get_channel_label(device_name: str, channel_num: int) -> str:
    side = "Left" if channel_num == 0 else "Right"
    return f"{device_name} ({side})"


# ─── LOGGING & UI ─────────────────────────────────────────────────────────────

def print_header(title: str, width: int = 50):
    console.print("=" * width, style="bold cyan")
    console.print(f"  {title}", style="bold cyan")
    console.print("=" * width, style="bold cyan")


def print_section(title: str):
    console.print(f"\n[bold yellow]→ {title}[/bold yellow]")


def print_ok(message: str):
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str):
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_error(message: str):
    console.print(f"[red]❌ {message}[/red]")


def print_info(message: str):
    console.print(f"[cyan]ℹ️  {message}[/cyan]")


def print_reminder(title: str, message: str):
    console.print(
        Panel(
            f"[bold]{message}[/bold]",
            title=f"📷  {title}",
            style="bold blue",
            expand=False,
        )
    )


# ─── DEVICE INFO TABLES ───────────────────────────────────────────────────────

def print_video_devices_table(devices: List[Dict]):
    table = Table(title="VIDEO DEVICES", show_header=True, header_style="bold magenta")
    table.add_column("Index", style="cyan", width=6)
    table.add_column("Device Name", style="green")
    table.add_column("Resolution", style="yellow")
    table.add_column("Status", style="yellow")

    for dev in devices:
        status = "✅ OK" if dev.get("available") else "❌ N/A"
        res = f"{dev.get('width', '?')}x{dev.get('height', '?')}" if dev.get("available") else "—"
        table.add_row(str(dev["index"]), dev["name"], res, status)

    console.print(table)


def print_audio_devices_table(devices: List[Dict], highlight_dji: bool = True):
    table = Table(title="AUDIO INPUT DEVICES", show_header=True, header_style="bold magenta")
    table.add_column("Index", style="cyan", width=6)
    table.add_column("Device Name", style="green")
    table.add_column("Ch", style="yellow", width=4)
    table.add_column("Sample Rate", style="yellow")
    table.add_column("DJI?", style="bold")

    for dev in devices:
        confirmed = is_dji_mic_device(dev.get("name", ""))
        dji_flag = "[bold green]✓ DJI[/bold green]" if confirmed else "—"
        # display_name carries "(receiver N)" suffix for identical-name devices
        display = dev.get("display_name", dev["name"])
        name_style = "[bold green]" + display + "[/bold green]" if confirmed and highlight_dji else display
        table.add_row(
            str(dev["index"]),
            name_style,
            str(dev.get("channels", "?")),
            str(dev.get("samplerate", "?")),
            dji_flag,
        )

    console.print(table)


# ─── AUDIO PROCESSING ─────────────────────────────────────────────────────────

def compute_rms_db(audio_chunk: np.ndarray, ref: float = 1.0) -> float:
    if len(audio_chunk) == 0:
        return -96.0
    rms = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))
    if rms <= 0:
        return -96.0
    return float(20 * np.log10(rms / ref + 1e-12))


def compute_peak_db(audio_chunk: np.ndarray, ref: float = 32768.0) -> float:
    if len(audio_chunk) == 0:
        return -96.0
    peak = np.max(np.abs(audio_chunk))
    if peak <= 0:
        return -96.0
    return float(20 * np.log10(peak / ref + 1e-12))


def get_vu_meter(db_level: float, width: int = 20, min_db: float = -60, max_db: float = 0) -> str:
    clipped = max(min_db, min(max_db, db_level))
    filled = int(((clipped - min_db) / (max_db - min_db)) * width)
    meter = "█" * filled + "░" * (width - filled)
    return f"[{meter}] {db_level:6.1f} dBFS"


def cross_correlate_audio(audio1: np.ndarray, audio2: np.ndarray, sr: int = 44100) -> Tuple[float, float]:
    a1 = audio1.astype(np.float64)
    a2 = audio2.astype(np.float64)
    a1 /= (np.max(np.abs(a1)) + 1e-10)
    a2 /= (np.max(np.abs(a2)) + 1e-10)

    correlation = signal.correlate(a1, a2, mode="full")
    lags = signal.correlation_lags(len(a1), len(a2), mode="full")
    max_idx = np.argmax(np.abs(correlation))
    offset_seconds = lags[max_idx] / sr
    corr_coeff = correlation[max_idx] / (np.sqrt(np.sum(a1 ** 2) * np.sum(a2 ** 2)) + 1e-10)
    return float(offset_seconds), float(corr_coeff)


def generate_sine_tone(
    frequency: float, duration: float, sr: int = 44100, amplitude: float = 0.3
) -> np.ndarray:
    t = np.arange(int(duration * sr)) / sr
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def apply_fade(audio: np.ndarray, fade_duration: float, sr: int = 44100, fade_type: str = "in") -> np.ndarray:
    fade_samples = min(int(fade_duration * sr), len(audio))
    curve = np.linspace(0, 1, fade_samples)
    out = audio.copy()
    if fade_type == "in":
        out[:fade_samples] *= curve
    else:
        out[-fade_samples:] *= curve[::-1]
    return out


# ─── FILE & PATH HELPERS ──────────────────────────────────────────────────────

def create_session_folder(base_dir: str = "outputs") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = Path(base_dir) / f"SESSION_{ts}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_session_log(session_folder: Path, log_data: Dict):
    log_file = session_folder / "session_log.json"
    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2, default=str)
    print_ok(f"Session log saved: {log_file}")


def save_device_assignments(assignments: Dict, output_file: str = "device_assignments.json"):
    with open(output_file, "w") as f:
        json.dump(assignments, f, indent=2)
    print_ok(f"Device assignments saved: {output_file}")


def load_device_assignments(input_file: str = "device_assignments.json") -> Optional[Dict]:
    if not os.path.exists(input_file):
        return None
    with open(input_file, "r") as f:
        return json.load(f)


def format_filesize(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─── FFMPEG POST-PROCESSING ───────────────────────────────────────────────────

def get_ffmpeg_path() -> Optional[str]:
    """Return path to ffmpeg binary or None if not found."""
    return shutil.which("ffmpeg")


def mux_video_audio(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    """
    Mux a video file with an audio file using ffmpeg.
    Video stream is copied; audio is re-encoded to AAC 192k.
    """
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        print_error("ffmpeg not found in PATH. Install via: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        return False

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print_error(f"ffmpeg error: {result.stderr.decode(errors='replace')[-200:]}")
        return False
    return True


def mux_session(session_folder: Path) -> None:
    """
    Mux each cam_{label}.mp4 with its mic_{label}.wav in the session folder.
    Produces cam_{label}_muxed.mp4 for each matched pair.
    """
    print_section("MUXING VIDEO + AUDIO")

    cam_files = sorted(session_folder.glob("cam_*.mp4"))
    if not cam_files:
        print_warning("No cam_*.mp4 files found in session folder")
        return

    any_done = False
    for cam_file in cam_files:
        label = cam_file.stem[4:]  # "cam_red" → "red"
        audio_file = session_folder / f"mic_{label}.wav"
        out_file = session_folder / f"cam_{label}_muxed.mp4"

        if not audio_file.exists():
            print_warning(f"Skipping {cam_file.name}: no matching mic_{label}.wav")
            continue

        print_info(f"  {cam_file.name} + mic_{label}.wav → {out_file.name}")
        if mux_video_audio(cam_file, audio_file, out_file):
            size = out_file.stat().st_size
            print_ok(f"  Created {out_file.name} ({format_filesize(size)})")
            any_done = True
        else:
            print_error(f"  Failed: {out_file.name}")

    if not any_done:
        print_warning("No pairs were muxed — verify cam_*.mp4 and mic_*.wav exist in session folder")


# ─── CHECK SUMMARY ────────────────────────────────────────────────────────────

def print_device_check_summary(check_results: Dict):
    console.print("\n")
    print_header("PRE-SESSION CHECK RESULTS", width=60)
    console.print()

    console.print("[bold cyan]VIDEO DEVICES[/bold cyan]")
    for cam_name, cam_result in check_results.get("cameras", {}).items():
        if cam_result["status"] == "ok":
            console.print(
                f"  [green]✅[/green] {cam_name}: {cam_result['resolution']} @ {cam_result['fps']:.1f} fps"
            )
        elif cam_result["status"] == "warning":
            console.print(
                f"  [yellow]⚠️ [/yellow] {cam_name}: {cam_result['resolution']} @ {cam_result['fps']:.1f} fps — {cam_result['warning']}"
            )
        else:
            console.print(f"  [red]❌[/red] {cam_name}: {cam_result.get('error', 'Error')}")

    console.print("\n[bold cyan]AUDIO DEVICES[/bold cyan]")
    for mic_name, mic_result in check_results.get("mics", {}).items():
        if mic_result["status"] == "ok":
            console.print(f"  [green]✅[/green] {mic_name}: avg {mic_result['level_db']:.1f} dBFS")
        elif mic_result["status"] == "warning":
            console.print(
                f"  [yellow]⚠️ [/yellow] {mic_name}: avg {mic_result.get('level_db', 0):.1f} dBFS — {mic_result['warning']}"
            )
        else:
            console.print(f"  [red]❌[/red] {mic_name}: {mic_result.get('error', 'Error')}")

    console.print()