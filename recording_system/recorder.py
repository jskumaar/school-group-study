"""
Main simultaneous recording logic: webcams + DJI microphones.

Key design decisions:
- WebcamRecorder threads write H.264 video to disk; also expose latest_frame_small
  for the live preview grid shown in the main thread.
- AudioRecorder uses sounddevice.InputStream + a queue consumed by a writer thread,
  so audio is written to disk incrementally rather than buffered in RAM.
  For a stereo DJI receiver (channels=2), the writer splits L and R to separate WAV files.
- Main thread runs the OpenCV preview loop and detects 'Q' for graceful shutdown.
- Files are named by participant label: cam_{label}.mp4 / mic_{label}.wav
"""

import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import sounddevice as sd
import soundfile as sf
from rich.console import Console

import config
from utils import (
    print_section, print_ok, print_warning, print_error, print_info,
    print_reminder, generate_sine_tone, apply_fade,
    format_duration, format_filesize,
    create_session_folder, save_session_log,
    mux_session, get_ffmpeg_path,
    label_color_bgr, open_video_capture,
)

console = Console()

_PREVIEW_W, _PREVIEW_H = 320, 240


# ─── WEBCAM RECORDER ──────────────────────────────────────────────────────────

class WebcamRecorder(threading.Thread):
    """Records video from one webcam. Exposes latest_frame_small for preview."""

    def __init__(
        self,
        device_index: int,
        label: str,
        output_file: Path,
        fps: int = config.TARGET_FPS,
        resolution: tuple = config.RESOLUTION,
        stop_event: threading.Event = None,
    ):
        super().__init__(daemon=True)
        self.device_index = device_index
        self.label = label
        self.output_file = output_file
        self.fps = fps
        self.resolution = resolution
        self.stop_event = stop_event or threading.Event()
        self.frame_count = 0
        self.dropped_frames = 0
        self.start_time: Optional[float] = None
        self.error: Optional[str] = None
        self._latest_small: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

    def get_preview_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return self._latest_small.copy() if self._latest_small is not None else None

    def run(self):
        cap = None
        writer = None
        try:
            cap = open_video_capture(self.device_index)
            if not cap.isOpened():
                self.error = f"Cannot open device {self.device_index}"
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            cap.set(cv2.CAP_PROP_FPS, self.fps)

            fourcc = cv2.VideoWriter_fourcc(*config.VIDEO_CODEC)
            writer = cv2.VideoWriter(str(self.output_file), fourcc, self.fps, self.resolution)
            if not writer.isOpened():
                self.error = "Cannot create video writer (codec issue?)"
                return

            self.start_time = time.perf_counter()
            print_ok(f"Webcam '{self.label}' (dev {self.device_index}) recording started")

            while not self.stop_event.is_set():
                ret, frame = cap.read()
                if ret:
                    if frame.shape[:2] != (self.resolution[1], self.resolution[0]):
                        frame = cv2.resize(frame, self.resolution)
                    writer.write(frame)
                    small = cv2.resize(frame, (_PREVIEW_W, _PREVIEW_H))
                    with self._frame_lock:
                        self._latest_small = small
                    self.frame_count += 1
                else:
                    self.dropped_frames += 1

        except Exception as e:
            self.error = str(e)
        finally:
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()
            elapsed = (time.perf_counter() - self.start_time) if self.start_time else 0
            print_ok(f"Webcam '{self.label}' stopped — {self.frame_count} frames in {elapsed:.1f}s")


# ─── AUDIO RECORDER ───────────────────────────────────────────────────────────

class AudioRecorder:
    """
    Records audio from one sounddevice input device.

    Stereo DJI receiver (channels=2, len(output_paths)==2):
      → records 2ch, writes L to output_paths[0], R to output_paths[1]

    Single mic (channels=1, len(output_paths)==1):
      → records 1ch, writes to output_paths[0]

    Audio is written to disk incrementally via a queue + writer thread, so
    RAM usage is O(queue size), not O(session length).
    """

    def __init__(
        self,
        device_index: int,
        name: str,
        output_paths: List[Path],
        sr: int = config.AUDIO_SAMPLERATE,
        channels: int = 1,
        stop_event: threading.Event = None,
    ):
        self.device_index = device_index
        self.name = name
        self.output_paths = [Path(p) for p in output_paths]
        self.sr = sr
        self.channels = channels
        self.stop_event = stop_event or threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=500)
        self._stream: Optional[sd.InputStream] = None
        self._writer_thread: Optional[threading.Thread] = None
        self.sample_count: int = 0
        self.start_time: Optional[float] = None
        self.error: Optional[str] = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        # Called from sounddevice C thread — no blocking I/O here.
        try:
            self._queue.put_nowait(indata.copy())
        except queue.Full:
            pass  # drop chunk on overflow rather than crash
        self.sample_count += frames

    def _write_loop(self):
        stereo_split = self.channels >= 2 and len(self.output_paths) >= 2
        try:
            if stereo_split:
                f_l = sf.SoundFile(str(self.output_paths[0]), "w", self.sr, 1, subtype="PCM_16")
                f_r = sf.SoundFile(str(self.output_paths[1]), "w", self.sr, 1, subtype="PCM_16")
                try:
                    while True:
                        try:
                            chunk = self._queue.get(timeout=0.5)
                            # chunk shape: (frames, channels) — float32
                            f_l.write(chunk[:, 0:1])
                            f_r.write(chunk[:, 1:2])
                        except queue.Empty:
                            if self.stop_event.is_set():
                                # Drain remaining chunks
                                while not self._queue.empty():
                                    chunk = self._queue.get_nowait()
                                    f_l.write(chunk[:, 0:1])
                                    f_r.write(chunk[:, 1:2])
                                break
                finally:
                    f_l.close()
                    f_r.close()
            else:
                with sf.SoundFile(str(self.output_paths[0]), "w", self.sr, 1, subtype="PCM_16") as f:
                    while True:
                        try:
                            chunk = self._queue.get(timeout=0.5)
                            mono = chunk[:, 0:1] if chunk.ndim == 2 else chunk.reshape(-1, 1)
                            f.write(mono)
                        except queue.Empty:
                            if self.stop_event.is_set():
                                while not self._queue.empty():
                                    chunk = self._queue.get_nowait()
                                    mono = chunk[:, 0:1] if chunk.ndim == 2 else chunk.reshape(-1, 1)
                                    f.write(mono)
                                break
        except Exception as e:
            self.error = str(e)
            print_error(f"Audio writer error ({self.name}): {e}")

    def start(self):
        self._writer_thread = threading.Thread(target=self._write_loop, daemon=True)
        self._writer_thread.start()
        try:
            self._stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.sr,
                channels=self.channels,
                callback=self._audio_callback,
                dtype="float32",
                blocksize=config.AUDIO_CHUNK_SIZE,
            )
            self._stream.start()
            self.start_time = time.perf_counter()
            labels = " + ".join(p.name for p in self.output_paths)
            print_ok(f"Audio recorder started: {self.name} → {labels}")
        except Exception as e:
            self.error = str(e)
            print_error(f"Cannot start audio device {self.device_index} ({self.name}): {e}")

    def stop(self):
        """Stop the input stream, then wait for the writer thread to drain the queue."""
        if self._stream:
            try:
                # abort() returns immediately (Pa_AbortStream); stop() can deadlock
                # on Windows WASAPI by waiting for callbacks while the GIL is held.
                self._stream.abort()
                self._stream.close()
            except Exception:
                pass
        # stop_event is already set by the caller; writer thread drains queue then exits
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=15)

    @property
    def duration(self) -> float:
        return (time.perf_counter() - self.start_time) if self.start_time else 0.0


# ─── SYNC TONE ────────────────────────────────────────────────────────────────

def play_sync_tone():
    """
    Play 3 × 200ms beeps at 1000 Hz through the default output device.
    This creates a visible transient in all audio waveforms (lavalier mics
    and Insta360 built-in mic) for post-processing alignment.
    """
    if not config.SYNC_TONE_ENABLED:
        return

    print_info("Playing sync tone (3 beeps)...")
    sr = 44100
    parts = []
    for _ in range(config.SYNC_TONE_NUM_BEEPS):
        beep = generate_sine_tone(config.SYNC_TONE_FREQUENCY, config.SYNC_TONE_DURATION, sr=sr, amplitude=0.35)
        beep = apply_fade(beep, 0.01, sr=sr, fade_type="in")
        beep = apply_fade(beep, 0.01, sr=sr, fade_type="out")
        parts.append(beep)
        parts.append(np.zeros(int(config.SYNC_TONE_GAP * sr), dtype=np.float32))
    sd.play(np.concatenate(parts), samplerate=sr)
    sd.wait()
    print_ok("Sync tone played — check all mic waveforms for the 3-beep spike")


# ─── LIVE PREVIEW GRID ────────────────────────────────────────────────────────

def _build_recording_grid(
    webcam_threads: Dict[str, "WebcamRecorder"],
    audio_recorders: List["AudioRecorder"],
    elapsed: float,
) -> np.ndarray:
    """
    Build a preview grid: one cell per participant (with colored border) + status panel.
    Layout: all participant cells side-by-side in a single row, status appended at right.
    """
    cells = []

    for label, t in webcam_threads.items():
        color = label_color_bgr(label)
        frame = t.get_preview_frame()
        if frame is None:
            cell = np.zeros((_PREVIEW_H, _PREVIEW_W, 3), dtype=np.uint8)
        else:
            cell = frame.copy()

        # Thick colored border to identify participant
        border = 5
        cv2.rectangle(cell, (0, 0), (_PREVIEW_W - 1, _PREVIEW_H - 1), color, border * 2)

        # Overlay label + stats
        fps_now = t.frame_count / max(elapsed, 0.1)
        info = f"{label}  {fps_now:.0f}fps  {t.frame_count}f"
        text_color = color if not t.error else (0, 0, 255)
        cv2.putText(cell, info, (border + 2, border + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, text_color, 1)
        if t.error:
            cv2.putText(cell, "ERROR", (4, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cells.append(cell)

    # Status panel
    status = np.zeros((_PREVIEW_H, _PREVIEW_W, 3), dtype=np.uint8)
    h = int(elapsed // 3600)
    m = int((elapsed % 3600) // 60)
    s = int(elapsed % 60)
    cv2.putText(status, f"{h:02d}:{m:02d}:{s:02d}", (10, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
    cv2.putText(status, "Press Q to stop", (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)

    for i, rec in enumerate(audio_recorders):
        y = 105 + i * 22
        color = (0, 200, 0) if not rec.error else (0, 0, 200)
        name_short = rec.name[:22]
        labels_str = " ".join(p.stem for p in rec.output_paths)
        cv2.putText(status, f"{labels_str}: {rec.sample_count // 1000}k smp",
                    (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
        cv2.putText(status, name_short, (5, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (160, 160, 160), 1)

    cells.append(status)

    # Arrange in rows of 4
    n = len(cells)
    if n <= 4:
        return np.hstack(cells)
    row1 = np.hstack(cells[:4])
    row2_cells = cells[4:]
    # Pad row2 to same width
    while len(row2_cells) < 4:
        row2_cells.append(np.zeros((_PREVIEW_H, _PREVIEW_W, 3), dtype=np.uint8))
    row2 = np.hstack(row2_cells)
    return np.vstack([row1, row2])


# ─── MAIN RECORDING SESSION ───────────────────────────────────────────────────

def run_recording_session(assignments: Dict) -> Optional[Path]:
    """
    Run the full simultaneous recording session.
    Returns path to session folder on success, None on failure.
    """
    print_section("STARTING RECORDING SESSION")

    session_folder = create_session_folder(str(config.OUTPUTS_DIR))
    print_ok(f"Session folder: {session_folder}")

    # Insta360 reminder — must be started manually before we begin
    print_reminder(
        "INSTA360 REMINDER",
        "Please START recording on the Insta360 NOW,\nthen press ENTER to begin the synchronized session.",
    )
    input("Press ENTER when Insta360 is recording...")

    stop_event = threading.Event()

    # ── Create and start webcam recorders (participant-keyed) ─────────────────
    webcam_threads: Dict[str, WebcamRecorder] = {}
    for p in assignments.get("participants", []):
        label = p["label"]
        idx = p["cam_device"]
        out = session_folder / f"cam_{label}.mp4"
        t = WebcamRecorder(idx, label, out, config.TARGET_FPS, config.RESOLUTION, stop_event)
        t.start()
        webcam_threads[label] = t

    # ── Create and start audio recorders (one per unique device) ─────────────
    audio_recorders: List[AudioRecorder] = []
    for adev in assignments.get("audio_devices", []):
        out_paths = [session_folder / f"{lbl}.wav" for lbl in adev["labels"]]
        # Use the device's native sample rate if available — WASAPI devices on
        # Windows report their native rate (often 48000) which must be used or
        # PortAudio will fail to open the stream.
        sr = adev.get("samplerate") or config.AUDIO_SAMPLERATE
        rec = AudioRecorder(
            device_index=adev["device"],
            name=adev["name"],
            output_paths=out_paths,
            sr=sr,
            channels=adev["channels"],
            stop_event=stop_event,
        )
        rec.start()
        audio_recorders.append(rec)

    if not webcam_threads and not audio_recorders:
        print_error("No devices started — check assignments and try again")
        return None

    # Warn immediately for any audio device that failed to open
    for rec in audio_recorders:
        if rec.error:
            print_error(f"Audio recorder failed to start: {rec.name} — {rec.error}")
    if any(r.error for r in audio_recorders):
        print_warning("Some audio devices could not be opened. Stop now (Q) and re-run option 1 to reassign.")

    # Wait for devices to initialize before playing the sync beep
    time.sleep(0.8)

    # ── Sync beep ─────────────────────────────────────────────────────────────
    sync_beep_time = datetime.now()
    play_sync_tone()

    recording_start = time.perf_counter()
    session_start_wall = datetime.now().isoformat()

    print_ok("Recording in progress. [bold]Press Q[/bold] in the preview window to stop.")

    # ── Preview loop (must run in main thread for OpenCV on macOS) ────────────
    try:
        while not stop_event.is_set():
            elapsed = time.perf_counter() - recording_start
            grid = _build_recording_grid(webcam_threads, audio_recorders, elapsed)
            cv2.imshow("Recording — Press Q to Stop", grid)
            key = cv2.waitKey(33) & 0xFF
            if key in (ord("q"), ord("Q"), 27):  # q, Q, or ESC
                stop_event.set()
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        cv2.destroyAllWindows()

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    print_info("Stopping recording — flushing audio buffers to disk...")
    stop_event.set()

    for rec in audio_recorders:
        rec.stop()  # blocks until queue is drained

    for t in webcam_threads.values():
        t.join(timeout=10)

    final_duration = time.perf_counter() - recording_start

    # ── Session log ───────────────────────────────────────────────────────────
    log = {
        "session": session_folder.name,
        "start_wall": session_start_wall,
        "sync_beep_time": sync_beep_time.isoformat(),
        "duration_seconds": final_duration,
        "assignments": assignments,
        "config": {
            "fps": config.TARGET_FPS,
            "resolution": list(config.RESOLUTION),
            "audio_sr": config.AUDIO_SAMPLERATE,
        },
        "streams": {},
    }

    for label, t in webcam_threads.items():
        log["streams"][f"cam_{label}"] = {
            "frames": t.frame_count,
            "dropped": t.dropped_frames,
            "error": t.error,
        }
    for rec in audio_recorders:
        for p in rec.output_paths:
            log["streams"][p.stem] = {
                "samples": rec.sample_count,
                "duration_s": rec.duration,
                "error": rec.error,
            }

    save_session_log(session_folder, log)

    # ── Insta360 stop reminder ────────────────────────────────────────────────
    print_reminder("INSTA360 REMINDER", "Please STOP recording on the Insta360 now.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print_section("RECORDING COMPLETE")
    console.print(f"[bold green]Duration:[/bold green] {format_duration(final_duration)}")
    console.print(f"[bold green]Output:[/bold green]   {session_folder}\n")

    for label, t in webcam_threads.items():
        f = session_folder / f"cam_{label}.mp4"
        size = f.stat().st_size if f.exists() else 0
        icon = "❌" if t.error else "✅"
        console.print(f"  {icon} cam_{label}.mp4   {t.frame_count} frames  ({format_filesize(size)})")
        if t.error:
            console.print(f"     [red]{t.error}[/red]")

    for rec in audio_recorders:
        for p in rec.output_paths:
            size = p.stat().st_size if p.exists() else 0
            icon = "❌" if rec.error else "✅"
            console.print(f"  {icon} {p.name}   {rec.sample_count} samples  ({format_filesize(size)})")
        if rec.error:
            console.print(f"     [red]{rec.error}[/red]")

    # ── Offer post-processing mux ─────────────────────────────────────────────
    if get_ffmpeg_path():
        try:
            do_mux = input("\nMux cam videos with audio files now? [y/N]: ").strip().lower()
            if do_mux == "y":
                mux_session(session_folder)
        except (EOFError, KeyboardInterrupt):
            pass
    else:
        print_warning("ffmpeg not found — skipping mux offer (install ffmpeg to enable)")

    return session_folder


if __name__ == "__main__":
    # Minimal smoke test with participant structure
    test_assignments = {
        "participants": [
            {"label": "red",  "cam_device": 0, "mic_device": 1, "mic_channel": 0,
             "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
            {"label": "blue", "cam_device": 2, "mic_device": 1, "mic_channel": 1,
             "mic_name": "DJI Mic 2 (Receiver)", "channels_on_device": 2},
        ],
        "audio_devices": [
            {"device": 1, "name": "DJI Mic 2 (Receiver)", "channels": 2,
             "labels": ["mic_red", "mic_blue"], "samplerate": 44100, "is_stereo_pair": True},
        ],
    }
    run_recording_session(test_assignments)