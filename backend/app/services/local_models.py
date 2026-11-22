import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Target filler words to detect hesitation/fluency patterns
FILLER_WORDS = {"um", "uh", "erm", "like", "basically", "literally"}
FILLER_PHRASES = ["sort of", "kind of"]
SELF_CORRECTION_PATTERNS = [
    re.compile(r"\bi mean\b", re.IGNORECASE),
    re.compile(r"\bwait no\b", re.IGNORECASE),
    re.compile(r"\bactually no\b", re.IGNORECASE),
    re.compile(r"\brather\b", re.IGNORECASE),
]
WORD_CLEAN_REGEX = re.compile(r"[^\w\s]")


class LocalMLService:
    """Thread-safe singleton managing on-machine CPU-only ML models.

    - Embeddings: BAAI/bge-small-en-v1.5 (384 dimensions)
    - Speech-to-Text & Prosody: faster-whisper (CPU, int8, word-level timestamps)
    """

    _instance: Optional["LocalMLService"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        embedding_model_name: Optional[str] = None,
        whisper_model_size: Optional[str] = None,
    ) -> None:
        self.embedding_model_name = (
            embedding_model_name
            or os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        )
        self.whisper_model_size = (
            whisper_model_size
            or os.getenv("WHISPER_MODEL_SIZE", "small")
        )

        self._embedding_model = None
        self._whisper_model = None
        self._inference_lock = threading.Lock()

        self._load_models()

    def _load_models(self) -> None:
        """Loads models into memory once during initialization."""
        logger.info("Initializing SentenceTransformer: %s", self.embedding_model_name)
        from sentence_transformers import SentenceTransformer

        self._embedding_model = SentenceTransformer(self.embedding_model_name)

        logger.info(
            "Initializing WhisperModel: size=%s, device=cpu, compute_type=int8",
            self.whisper_model_size,
        )
        from faster_whisper import WhisperModel

        self._whisper_model = WhisperModel(
            self.whisper_model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Local ML models loaded successfully.")

    @classmethod
    def get_instance(
        cls,
        embedding_model_name: Optional[str] = None,
        whisper_model_size: Optional[str] = None,
    ) -> "LocalMLService":
        """Thread-safe accessor for the singleton LocalMLService instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        embedding_model_name=embedding_model_name,
                        whisper_model_size=whisper_model_size,
                    )
        return cls._instance

    @property
    def is_ready(self) -> bool:
        """Returns True if both embedding and whisper models are loaded."""
        return self._embedding_model is not None and self._whisper_model is not None

    def health_check(self) -> Dict[str, Any]:
        """Performs a self-diagnostic check on local ML models."""
        return {
            "embeddings": "ready" if self._embedding_model is not None else "not_loaded",
            "whisper": "ready" if self._whisper_model is not None else "not_loaded",
            "embedding_model": self.embedding_model_name,
            "whisper_model_size": self.whisper_model_size,
            "status": "ready" if self.is_ready else "degraded",
        }

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Computes 384-dimensional normalized vector embeddings for input strings.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 384-element float vectors.
        """
        if not texts:
            return []

        with self._inference_lock:
            embeddings = self._embedding_model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.tolist()

    def analyze_voice(
        self, audio_path: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Transcribes student audio and extracts cognitive fluency & prosody metrics.

        Args:
            audio_path: Local filesystem path to the audio file.
            language: Language code to enforce (defaults to English 'en').

        Returns:
            Dictionary containing:
                - transcript (str): Full transcribed response.
                - speech_rate_wpm (float): Words per minute.
                - hesitation_pause_count (int): Inter-word gaps > 1.5 seconds.
                - max_pause_sec (float): Longest pause duration in seconds.
                - filler_word_ratio (float): Ratio of filler words to total words.
                - monotone_recitation_flag (bool): Flag for potential rote memorization.
        """
        with self._inference_lock:
            segments, info = self._whisper_model.transcribe(
                audio_path,
                language=language,
                word_timestamps=True,
                vad_filter=True,
            )
            # Evaluate the generator into a list
            segment_list = list(segments)

        words_data = []
        transcript_parts = []

        for seg in segment_list:
            if seg.text:
                transcript_parts.append(seg.text.strip())
            if seg.words:
                words_data.extend(seg.words)

        full_transcript = " ".join(transcript_parts).strip()
        total_words = len(words_data)

        # 1. Calculate inter-word gaps and hesitation pauses (> 1.5 seconds)
        hesitation_pause_count = 0
        max_pause_sec = 0.0

        for i in range(len(words_data) - 1):
            current_end = words_data[i].end
            next_start = words_data[i + 1].start
            gap = next_start - current_end
            if gap > 0:
                if gap > max_pause_sec:
                    max_pause_sec = gap
                if gap > 1.5:
                    hesitation_pause_count += 1

        # 2. Calculate speech duration and Words Per Minute (WPM)
        duration_sec = 0.0
        if info and hasattr(info, "duration") and info.duration and info.duration > 0:
            duration_sec = float(info.duration)
        elif words_data:
            duration_sec = max(0.1, words_data[-1].end - words_data[0].start)

        if duration_sec > 0 and total_words > 0:
            speech_rate_wpm = round((total_words / duration_sec) * 60.0, 2)
        else:
            speech_rate_wpm = 0.0

        # 3. Filler word ratio detection (single tokens + 2-word phrases)
        filler_count = 0
        for w in words_data:
            clean_word = WORD_CLEAN_REGEX.sub("", w.word.strip().lower())
            if clean_word in FILLER_WORDS:
                filler_count += 1

        lower_transcript = full_transcript.lower()
        for phrase in FILLER_PHRASES:
            matches = len(re.findall(r"\b" + re.escape(phrase) + r"\b", lower_transcript))
            filler_count += matches

        filler_word_ratio = (
            round(filler_count / max(total_words, 1), 4) if total_words > 0 else 0.0
        )

        # 4. Self-correction and phrase restarts
        self_correction_count = 0
        for pattern in SELF_CORRECTION_PATTERNS:
            self_correction_count += len(pattern.findall(lower_transcript))

        # 5. Monotone recitation / rote memorization heuristic
        # Flag rapid, unreflective rote memorization: >= 15 words, > 170 WPM, 0 hesitation pauses, 0 self-corrections
        monotone_recitation_flag = bool(
            total_words >= 15
            and speech_rate_wpm > 170.0
            and hesitation_pause_count == 0
            and self_correction_count == 0
        )

        # 6. High-level qualitative fluency signal
        if monotone_recitation_flag:
            fluency_signal = "Rushed Recitation — Try Explaining Why"
        elif hesitation_pause_count >= 2 or filler_word_ratio > 0.12:
            fluency_signal = "Deliberative Hesitation — Exploring Mechanics"
        else:
            fluency_signal = "Natural Causal Reasoning"

        return {
            "transcript": full_transcript,
            "speech_rate_wpm": speech_rate_wpm,
            "hesitation_pause_count": hesitation_pause_count,
            "max_pause_sec": round(max_pause_sec, 2),
            "filler_word_ratio": filler_word_ratio,
            "self_correction_count": self_correction_count,
            "monotone_recitation_flag": monotone_recitation_flag,
            "fluency_signal": fluency_signal,
            "total_words": total_words,
        }
