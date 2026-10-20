"""
Main entry point for the CMU child collaboration study recording system.
"""

import os
import sys
import threading
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from utils import (
    print_section, print_ok, print_warning, print_error, print_info,
    save_device_assignments, load_device_assignments,
    mux_session, get_ffmpeg_path,
)
from device_checker import (
    discover_video_devices,
    discover_audio_devices,
    assign_participants_interactive,
    run_hardware_check,
)
from audio_checker import run_dominance_check
from calibration import run_camera_calibration
from recorder import run_recording_session
from sync_finder import find_sync_offset

console = Console()

ASSIGNMENTS_FILE = "device_assignments.json"


# ─── MENU ─────────────────────────────────────────────────────────────────────

def print_main_menu(assignments_loaded: bool):
    status = "[green]✓ devices assigned[/green]" if assignments_loaded else "[yellow]⚠ no assignments yet[/yellow]"
    menu_text = f"""
[bold cyan]   CMU Child Collaboration Study — Multi-Device Recorder v1.0[/bold cyan]
   {status}

   [bold][1][/bold] Discover & assign devices
   [bold][2][/bold] Run pre-session hardware check
   [bold][3][/bold] Run dominant speaker consistency check
   [bold][4][/bold] Run camera calibration
   [bold][5][/bold] Start recording session
   [bold][6][/bold] Mux last session (cam video + mic audio)
   [bold][7][/bold] Find sync offset (Insta360 alignment)
   [bold][Q][/bold] Quit
"""
    console.print(Panel(menu_text, style="bold blue"))


# ─── MENU HANDLERS ────────────────────────────────────────────────────────────

def menu_discover_devices() -> dict:
    print_section("DISCOVERING DEVICES")
    print_info("Scanning video devices (indices 0–14)…")
    video_devices = discover_video_devices(max_index=15)
    print_ok(f"Found {len(video_devices)} video device(s)")

    print_info("Scanning audio input devices…")
    audio_devices = discover_audio_devices()
    print_ok(f"Found {len(audio_devices)} audio device(s)")

    assignments = assign_participants_interactive(video_devices, audio_devices)
    save_device_assignments(assignments, ASSIGNMENTS_FILE)
    return assignments


def menu_hardware_check(assignments: dict):
    if not assignments:
        print_error("No device assignments found. Run option 1 first.")
        return
    run_hardware_check(assignments)


def menu_dominance_check(assignments: dict):
    if not assignments:
        print_error("No device assignments found. Run option 1 first.")
        return

    if not assignments.get("participants"):
        print_error("No participant assignments found. Run option 1 first.")
        return

    run_dominance_check(assignments)


def menu_camera_calibration(assignments: dict):
    if not assignments:
        print_error("No device assignments found. Run option 1 first.")
        return

    # Build {webcam_N: device_index} from participants list for calibration
    webcam_assignments = {}
    for i, p in enumerate(assignments.get("participants", []), start=1):
        webcam_assignments[f"webcam_{i}"] = p["cam_device"]
    run_camera_calibration(webcam_assignments)


def menu_start_recording(assignments: dict) -> Path:
    if not assignments:
        print_error("No device assignments found. Run option 1 first.")
        return None

    print_section("PRE-RECORDING CHECKLIST")
    checklist = [
        "All cameras are positioned and focused",
        "All lavalier mics are clipped on and transmitters are on",
        "DJI receiver(s) are connected and showing signal",
        "Insta360 is mounted and battery is charged",
        "Recording space has acceptable ambient noise level",
    ]
    for i, item in enumerate(checklist, 1):
        answer = Prompt.ask(f"  [{i}/{len(checklist)}] {item}?", choices=["y", "n"], default="y")
        if answer.lower() != "y":
            print_warning("Resolve checklist items before starting. Returning to menu.")
            return None

    print_ok("Checklist passed!")
    return run_recording_session(assignments)


def menu_mux_session(last_session_dir: Path):
    if not get_ffmpeg_path():
        print_error("ffmpeg not found. Install it: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        return

    if last_session_dir and last_session_dir.is_dir():
        console.print(f"Last session: [cyan]{last_session_dir}[/cyan]")
        use_last = Prompt.ask("Mux this session?", choices=["y", "n"], default="y")
        if use_last.lower() == "y":
            mux_session(last_session_dir)
            return

    path_str = Prompt.ask("Enter session folder path")
    session_path = Path(path_str)
    if not session_path.is_dir():
        print_error(f"Not a directory: {session_path}")
        return
    mux_session(session_path)


def menu_sync_finder():
    print_section("SYNC FINDER — ALIGN INSTA360 WITH LAVALIER MICS")
    console.print("[dim]Load the Insta360 audio as a WAV (export from the Insta360 app or use ffmpeg to extract).[/dim]\n")

    insta360_file = Prompt.ask("Path to Insta360 audio WAV")
    reference_file = Prompt.ask("Path to reference lavalier mic WAV (e.g. mic1.wav)")

    insta360_path = Path(insta360_file)
    reference_path = Path(reference_file)

    if not insta360_path.exists():
        print_error(f"File not found: {insta360_path}")
        return
    if not reference_path.exists():
        print_error(f"File not found: {reference_path}")
        return

    result = find_sync_offset(insta360_path, reference_path)
    if result:
        offset, corr = result
        console.print(f"\n[bold green]Sync result:[/bold green]")
        console.print(f"  Insta360 vs {reference_path.name}: [bold]{offset:+.3f}[/bold] seconds")
        if offset > 0:
            console.print(f"  → Insta360 started {offset:.3f}s AFTER the lavalier mics")
        elif offset < 0:
            console.print(f"  → Insta360 started {-offset:.3f}s BEFORE the lavalier mics")
        else:
            console.print("  → Recordings are synchronized!")
        console.print(f"  Correlation coefficient: {corr:.4f}")
        console.print("\n[bold cyan]ffmpeg trim command:[/bold cyan]")
        if offset > 0:
            console.print(f"  ffmpeg -i insta360.mp4 -ss {offset:.3f} -c copy insta360_aligned.mp4")
        else:
            console.print(f"  ffmpeg -i mic1.wav -ss {-offset:.3f} -c copy mic1_aligned.wav")


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main():
    print_section("CMU CHILD COLLABORATION STUDY — RECORDING SYSTEM")

    current_assignments = load_device_assignments(ASSIGNMENTS_FILE)
    if current_assignments:
        print_ok(f"Loaded previous device assignments from {ASSIGNMENTS_FILE}")
    else:
        print_info("No saved assignments found. Start with option 1.")

    last_session_dir: Path = None

    while True:
        print_main_menu(bool(current_assignments))

        choice = Prompt.ask("[bold cyan]Select an option[/bold cyan]", default="Q").strip().upper()

        if choice == "1":
            current_assignments = menu_discover_devices()

        elif choice == "2":
            menu_hardware_check(current_assignments)

        elif choice == "3":
            menu_dominance_check(current_assignments)

        elif choice == "4":
            menu_camera_calibration(current_assignments)

        elif choice == "5":
            result = menu_start_recording(current_assignments)
            if result:
                last_session_dir = result

        elif choice == "6":
            menu_mux_session(last_session_dir)

        elif choice == "7":
            menu_sync_finder()

        elif choice == "Q":
            print_ok("Goodbye!")
            sys.exit(0)

        else:
            print_error("Invalid option. Enter 1–7 or Q.")

        try:
            input("\nPress ENTER to return to menu...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nInterrupted.")
        # Arm a hard-kill timer: if cleanup hangs (e.g. a PortAudio/WASAPI deadlock),
        # os._exit forcibly terminates all threads after 5 seconds.
        _kill = threading.Timer(5.0, os._exit, args=(1,))
        _kill.daemon = True
        _kill.start()
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)