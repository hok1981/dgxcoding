"""
Speech-to-text using faster-whisper.
Records from microphone until silence, then transcribes.
"""

import io
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000


class STT:
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        print(f"[STT] Loading Whisper {model_size} on {device}...")
        self.model = WhisperModel(model_size, device=device, compute_type="int8")
        print("[STT] Ready.")

    def record(self, silence_threshold_ms: int = 500, max_seconds: int = 30) -> np.ndarray:
        """
        Record from microphone. Stops after silence_threshold_ms of quiet.
        Returns audio as float32 numpy array at 16kHz.
        """
        silence_samples = int(SAMPLE_RATE * silence_threshold_ms / 1000)
        chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks
        energy_threshold = 0.01

        print("[STT] Listening... (speak now)")
        audio_chunks = []
        silent_samples = 0
        recording_started = False

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            while True:
                chunk, _ = stream.read(chunk_size)
                chunk = chunk.flatten()
                energy = np.sqrt(np.mean(chunk**2))

                if energy > energy_threshold:
                    recording_started = True
                    silent_samples = 0
                    audio_chunks.append(chunk)
                elif recording_started:
                    silent_samples += chunk_size
                    audio_chunks.append(chunk)
                    if silent_samples >= silence_samples:
                        break

                total_samples = sum(len(c) for c in audio_chunks)
                if total_samples >= SAMPLE_RATE * max_seconds:
                    break

        if not audio_chunks:
            return np.array([], dtype=np.float32)

        return np.concatenate(audio_chunks)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio array to text."""
        if len(audio) == 0:
            return ""
        segments, _ = self.model.transcribe(audio, beam_size=5, language="en")
        return " ".join(s.text.strip() for s in segments).strip()

    def listen(self, silence_threshold_ms: int = 500) -> str:
        """Record and transcribe in one call."""
        audio = self.record(silence_threshold_ms=silence_threshold_ms)
        text = self.transcribe(audio)
        print(f"[STT] Heard: {text!r}")
        return text
