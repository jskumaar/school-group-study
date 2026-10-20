"""
Dominant speaker consistency check.

Records 15 seconds from ALL mic channels simultaneously, then computes:
  - Which mic dominates in each 0.5s window (speaker identification proxy)
  - Crosstalk ratio for each mic (target energy vs. average of others)

Usage:
  run_dominance_check(assignments)  # pass full device_assignments dict
"""

import threading
import time
from typing import Dict, List, Optional

import numpy as np
import sounddevice as sd
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

import config
from utils import (
    print_section, print_ok, print_warning, print_error, print_info,
    compute_rms_db,
)

console = Console()


# ─── SIMULTANEOUS MULTI-DEVICE RECORDING ─────────────────────────────────────

def _record_device(device_index: int, channels: int, sr: int, duration: float, result: dict):
    """
    Record from one device for `duration` seconds using sd.InputStream.
    Stores the raw (n_samples, channels) float32 array in result["data"].
    This function is run in a thread so multiple devices record simultaneously.
    """
    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())

    try:
        with sd.InputStream(device=device_index, samplerate=sr, channels=channels,
                            dtype="float32", callback=callback):
            time.sleep(duration)

        if chunks:
            result["data"] = np.vstack(chunks)  # shape: (total_frames, channels)
        else:
            result["error"] = "No audio captured"
    except Exception as e:
        result["error"] = str(e)


def record_voice_baseline_simultaneous(
    mic_channels: List[Dict],
    duration: float = config.VOICE_BASELINE_DURATION,
    sr: int = config.AUDIO_SAMPLERATE,
) -> Dict[str, Optional[np.ndarray]]:
    """
    Record from all assigned mic channels simultaneously.

    mic_channels: list of dicts built from assignments["audio_devices"], each:
      {"device": int, "channel": int, "record_channels": int, "label": str}

    Returns: {label: mono_float32_array_or_None}
    """
    # Group by unique device_index so each physical device is opened only once
    device_map: Dict[int, Dict] = {}
    for mc in mic_channels:
        dev = mc["device"]
        if dev not in device_map:
            device_map[dev] = {
                "channels": mc["record_channels"],
                "labels_by_channel": {},
                "samplerate": mc.get("samplerate", sr),
            }
        device_map[dev]["labels_by_channel"][mc["channel"]] = mc["label"]

    raw_results: Dict[int, dict] = {dev: {"data": None, "error": None} for dev in device_map}
    threads = []

    for dev_idx, info in device_map.items():
        t = threading.Thread(
            target=_record_device,
            args=(dev_idx, info["channels"], info["samplerate"], duration, raw_results[dev_idx]),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=duration + 5)

    # Extract per-label mono arrays
    labeled: Dict[str, Optional[np.ndarray]] = {}
    for dev_idx, info in device_map.items():
        raw = raw_results[dev_idx].get("data")
        err = raw_results[dev_idx].get("error")

        if err:
            print_error(f"Device {dev_idx} recording failed: {err}")

        for ch_idx, label in info["labels_by_channel"].items():
            if raw is None:
                labeled[label] = None
            elif raw.ndim == 1:
                labeled[label] = raw
            else:
                ch = min(ch_idx, raw.shape[1] - 1)
                labeled[label] = raw[:, ch]

    return labeled


# ─── DOMINANCE ANALYSIS ───────────────────────────────────────────────────────

def analyze_dominance(
    recordings: Dict[str, Optional[np.ndarray]],
    window_duration: float = config.VOICE_BASELINE_WINDOW,
    sr: int = config.AUDIO_SAMPLERATE,
) -> Dict:
    """
    Segment all recordings into `window_duration`-second windows.
    For each window, identify which mic has the highest RMS energy.
    Returns dominance counts/percentages and per-window detail.
    """
    labels = [l for l, d in recordings.items() if d is not None]
    if not labels:
        return {}

    window_samples = int(window_duration * sr)
    arrays = {l: recordings[l] for l in labels}

    max_samples = max(len(a) for a in arrays.values())
    num_windows = max(1, max_samples // window_samples)

    dominance_counts = {l: 0 for l in labels}
    window_results = []

    for w in range(num_windows):
        s = w * window_samples
        e = s + window_samples
        rms_per_label = {}
        for label, audio in arrays.items():
            chunk = audio[s:e] if e <= len(audio) else audio[s:]
            if len(chunk) == 0:
                rms_per_label[label] = -96.0
            else:
                int16 = (chunk * 32767).astype(np.int16)
                rms_per_label[label] = compute_rms_db(int16, ref=32768)

        dominant = max(rms_per_label, key=rms_per_label.get)
        dominance_counts[dominant] += 1
        window_results.append({"window": w, "dominant": dominant, "rms": rms_per_label})

    total = sum(dominance_counts.values())
    pcts = {l: (dominance_counts[l] / total * 100 if total else 0.0) for l in labels}

    return {
        "labels": labels,
        "dominance_counts": dominance_counts,
        "dominance_pcts": pcts,
        "total_windows": total,
        "window_results": window_results,
    }


def analyze_crosstalk(
    recordings: Dict[str, Optional[np.ndarray]],
    window_duration: float = config.VOICE_BASELINE_WINDOW,
    sr: int = config.AUDIO_SAMPLERATE,
) -> Dict[str, float]:
    """
    For each mic, compute average (target RMS) / (mean other RMS) in dB.
    High ratio = low crosstalk = good placement.
    """
    labels = [l for l, d in recordings.items() if d is not None]
    if len(labels) < 2:
        return {}

    window_samples = int(window_duration * sr)
    arrays = {l: recordings[l] for l in labels}
    max_samples = max(len(a) for a in arrays.values())
    num_windows = max(1, max_samples // window_samples)

    ratios: Dict[str, float] = {}

    for target_label in labels:
        target_energy = []
        other_energy = []

        for w in range(num_windows):
            s = w * window_samples
            e = s + window_samples

            def rms_lin(audio):
                chunk = audio[s:e] if e <= len(audio) else audio[s:]
                return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2))) if len(chunk) else 0.0

            target_energy.append(rms_lin(arrays[target_label]))
            others = [rms_lin(arrays[l]) for l in labels if l != target_label]
            other_energy.append(float(np.mean(others)) if others else 0.0)

        t_avg = float(np.mean(target_energy)) + 1e-10
        o_avg = float(np.mean(other_energy)) + 1e-10
        ratios[target_label] = 20.0 * float(np.log10(t_avg / o_avg))

    return ratios


# ─── MAIN CHECK ENTRYPOINT ────────────────────────────────────────────────────

def run_dominance_check(assignments: Dict) -> Dict:
    """
    Run the full dominant speaker consistency check from device assignments.
    Accepts the dict structure produced by assign_participants_interactive().
    Reports dominance by participant label ("red", "blue", "green").
    """
    print_section("DOMINANT SPEAKER CONSISTENCY CHECK")

    # Build a device → samplerate lookup from the audio_devices list
    dev_sr = {
        adev["device"]: adev.get("samplerate", config.AUDIO_SAMPLERATE)
        for adev in assignments.get("audio_devices", [])
    }

    # Build mic_channels list from assignments["participants"]
    mic_channels: List[Dict] = []
    for p in assignments.get("participants", []):
        mic_channels.append({
            "device": p["mic_device"],
            "channel": p["mic_channel"],
            "record_channels": p["channels_on_device"],
            "label": p["label"],
            "device_name": p["mic_name"],
            "samplerate": dev_sr.get(p["mic_device"], config.AUDIO_SAMPLERATE),
        })

    if not mic_channels:
        print_error("No audio devices found in assignments. Run option 1 first.")
        return {}

    labels_str = ", ".join(mc["label"] for mc in mic_channels)
    console.print(f"[cyan]Channels to check:[/cyan] {labels_str}")
    console.print(f"[cyan]Duration:[/cyan] {config.VOICE_BASELINE_DURATION} seconds\n")

    console.print("[bold yellow]Ask each child to say their name and a few sentences, one at a time.[/bold yellow]")
    input("Press ENTER when ready to start recording the baseline...")

    # Countdown
    for i in range(3, 0, -1):
        console.print(f"  Starting in {i}...")
        time.sleep(1)
    console.print("[bold green]Recording![/bold green]")

    recordings = record_voice_baseline_simultaneous(
        mic_channels,
        duration=config.VOICE_BASELINE_DURATION,
        sr=config.AUDIO_SAMPLERATE,
    )

    none_labels = [l for l, d in recordings.items() if d is None]
    if none_labels:
        print_warning(f"No data captured for: {', '.join(none_labels)}")

    if all(d is None for d in recordings.values()):
        print_error("All recordings failed. Check device connections.")
        return {}

    print_ok("Baseline recording complete")

    # ── Dominance analysis ────────────────────────────────────────────────────
    dominance = analyze_dominance(recordings)
    crosstalk = analyze_crosstalk(recordings)

    # ── Report ────────────────────────────────────────────────────────────────
    print_section("DOMINANT SPEAKER CHECK RESULTS")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Mic", style="cyan")
    table.add_column("Dominant in", style="white")
    table.add_column("Crosstalk ratio", style="white")
    table.add_column("Status", style="bold")

    threshold = config.DOMINANCE_THRESHOLD_PCT * 100
    ct_threshold = config.CROSSTALK_WARNING_DB

    for label in dominance.get("labels", []):
        pct = dominance["dominance_pcts"].get(label, 0.0)
        ct_db = crosstalk.get(label, 0.0)

        if pct >= threshold and ct_db >= ct_threshold:
            status = "[green]✅ Good[/green]"
        elif pct >= 50 or ct_db >= ct_threshold - 5:
            status = "[yellow]⚠️  Moderate[/yellow]"
        else:
            status = "[red]❌ High crosstalk[/red]"

        table.add_row(label, f"{pct:.1f}%", f"{ct_db:+.1f} dB", status)

    console.print(table)

    # Recommendations
    console.print()
    any_bad = False
    for label in dominance.get("labels", []):
        pct = dominance["dominance_pcts"].get(label, 0.0)
        ct_db = crosstalk.get(label, 0.0)
        if pct < 50:
            print_warning(f"{label}: dominant only {pct:.0f}% — HIGH crosstalk, reposition mic closer to child's mouth")
            any_bad = True
        elif ct_db < ct_threshold:
            print_warning(f"{label}: only {ct_db:.0f} dB above others — consider repositioning")

    if not any_bad:
        print_ok("All mics show acceptable dominance. Placement looks good.")

    # Offer re-run
    try:
        redo = input("\nRe-run the check after adjusting mic placement? [y/N]: ").strip().lower()
        if redo == "y":
            return run_dominance_check(assignments)
    except (EOFError, KeyboardInterrupt):
        pass

    return {"dominance": dominance, "crosstalk": crosstalk}


if __name__ == "__main__":
    # Minimal test with two-channel DJI receiver + one BT mic
    test_assignments = {
        "participants": [
            {"label": "red",   "mic_device": 1, "mic_channel": 0,
             "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
            {"label": "blue",  "mic_device": 1, "mic_channel": 1,
             "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
            {"label": "green", "mic_device": 3, "mic_channel": 0,
             "mic_name": "DJI Mic BT", "channels_on_device": 1},
        ],
    }
    run_dominance_check(test_assignments)