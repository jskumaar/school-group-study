"""
Sync finder: cross-correlate Insta360 and lavalier audio to find timing offset.

Use this to align Insta360 footage with other recording streams in post-processing.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal
from rich.console import Console
from rich.prompt import Prompt

from utils import cross_correlate_audio, print_section, print_ok, print_info, print_error

console = Console()


def find_sync_offset(
    insta360_audio_file: Path, reference_audio_file: Path
) -> Optional[Tuple[float, float]]:
    """
    Find the timing offset between Insta360 audio and a reference lavalier mic WAV.

    Both files are expected to contain the 3-beep sync tone captured at session start.
    A positive offset means the Insta360 recording started AFTER the lavalier mics.

    Returns (offset_seconds, correlation_coefficient) or None on failure.
    """
    print_info(f"Loading Insta360 audio: {insta360_audio_file}")
    try:
        insta360_audio, sr1 = sf.read(insta360_audio_file)
    except Exception as e:
        print_error(f"Failed to load Insta360 audio: {e}")
        return None

    print_info(f"Loading reference audio: {reference_audio_file}")
    try:
        reference_audio, sr2 = sf.read(reference_audio_file)
    except Exception as e:
        print_error(f"Failed to load reference audio: {e}")
        return None

    # Resample to common sample rate if needed
    if sr1 != sr2:
        print_info(f"Sample rates differ: Insta360={sr1}Hz, Ref={sr2}Hz — resampling to {min(sr1, sr2)}Hz")
        target_sr = min(sr1, sr2)
        if sr1 != target_sr:
            insta360_audio = signal.resample(insta360_audio, int(len(insta360_audio) * target_sr / sr1))
        if sr2 != target_sr:
            reference_audio = signal.resample(reference_audio, int(len(reference_audio) * target_sr / sr2))
        sr = target_sr
    else:
        sr = sr1

    # Mix to mono
    if insta360_audio.ndim > 1:
        insta360_audio = insta360_audio.mean(axis=1)
    if reference_audio.ndim > 1:
        reference_audio = reference_audio.mean(axis=1)

    print_ok(f"Insta360: {len(insta360_audio)} samples ({len(insta360_audio)/sr:.1f}s)")
    print_ok(f"Reference: {len(reference_audio)} samples ({len(reference_audio)/sr:.1f}s)")

    print_info("Cross-correlating…")
    offset_seconds, corr_coeff = cross_correlate_audio(insta360_audio, reference_audio, sr=sr)
    print_ok(f"Offset: {offset_seconds:+.3f}s  (correlation: {corr_coeff:.3f})")

    return offset_seconds, corr_coeff


def main():
    """Standalone CLI for finding sync offset."""
    print_section("SYNC FINDER")
    print_info("Finds the timing offset between Insta360 and lavalier mic recordings.")
    print_info("Both files must contain the 3-beep sync tone from the recording session.")

    insta360_file = Prompt.ask("Path to Insta360 audio WAV")
    reference_file = Prompt.ask("Path to reference lavalier mic WAV (e.g. mic1.wav)")

    insta360_path = Path(insta360_file)
    reference_path = Path(reference_file)

    if not insta360_path.exists():
        print_error(f"File not found: {insta360_path}")
        sys.exit(1)
    if not reference_path.exists():
        print_error(f"File not found: {reference_path}")
        sys.exit(1)

    result = find_sync_offset(insta360_path, reference_path)

    if result:
        offset, corr = result

        console.print(f"\n[bold green]Sync Offset:[/bold green]")
        # reference_path (not reference_file) is the Path object with .name
        console.print(f"  Insta360 relative to {reference_path.name}: {offset:+.3f} seconds")

        if offset > 0:
            console.print(f"  → Insta360 started {offset:.3f}s AFTER the lavalier mics")
        elif offset < 0:
            console.print(f"  → Insta360 started {-offset:.3f}s BEFORE the lavalier mics")
        else:
            console.print("  → Recordings are synchronized!")

        console.print(f"  Correlation coefficient: {corr:.4f}")
        if abs(corr) > 0.8:
            console.print("  [green]High confidence[/green]")
        elif abs(corr) > 0.5:
            console.print("  [yellow]Moderate confidence[/yellow]")
        else:
            console.print("  [red]Low confidence — verify sync beep is present in both files[/red]")

        console.print(f"\n[bold cyan]Post-processing commands:[/bold cyan]")
        if offset > 0:
            console.print(f"  # Trim Insta360 to align with lavalier mics:")
            console.print(f"  ffmpeg -i insta360.mp4 -ss {offset:.3f} -c copy insta360_aligned.mp4")
        else:
            console.print(f"  # Trim lavalier mics to align with Insta360:")
            console.print(f"  ffmpeg -i mic1.wav -ss {-offset:.3f} -c copy mic1_aligned.wav")
        console.print(f"  # DaVinci Resolve: offset Insta360 clip by {offset:+.3f}s on timeline")
    else:
        print_error("Failed to find sync offset")
        sys.exit(1)


if __name__ == "__main__":
    main()