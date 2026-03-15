from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment]
    language: str
    duration: float


class WhisperService:
    def __init__(self, model_size: str = "base"):
        logger.info("Loading faster-whisper model: %s", model_size)
        self.model = WhisperModel(model_size, compute_type="int8")
        logger.info("Whisper model loaded successfully")

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> TranscriptResult:
        """Transcribe audio file. Runs blocking whisper in a thread."""
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> TranscriptResult:
        segments_gen, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
        )

        segments = []
        for seg in segments_gen:
            segments.append(TranscriptSegment(
                start=round(seg.start, 2),
                end=round(seg.end, 2),
                text=seg.text.strip(),
            ))

        return TranscriptResult(
            segments=segments,
            language=info.language,
            duration=info.duration,
        )
