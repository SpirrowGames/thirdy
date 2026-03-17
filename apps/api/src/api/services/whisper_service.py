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
    # Map model sizes to local paths (pre-downloaded models)
    _LOCAL_MODEL_PATHS = {
        "large-v3": "/app/models/whisper-large-v3",
    }

    def __init__(self, model_size: str = "base"):
        import os
        # Use local path if available, otherwise download from HuggingFace
        local_path = self._LOCAL_MODEL_PATHS.get(model_size)
        if local_path and os.path.isdir(local_path):
            logger.info("Loading faster-whisper model from local path: %s", local_path)
            model_id = local_path
        else:
            logger.info("Loading faster-whisper model: %s", model_size)
            model_id = model_size
        self.model = WhisperModel(model_id, compute_type="int8")
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
