"""
Audio processing utilities for concatenation, crossfading, and format conversion
"""
import io
from typing import List
from pydub import AudioSegment
from pydub.effects import normalize
import structlog
from config import settings

logger = structlog.get_logger()


class AudioProcessor:
    """
    Handles audio processing operations:
    - Concatenation of audio clips
    - Crossfading for smooth transitions
    - Format conversion and compression
    - Normalization
    """

    def __init__(self):
        self.crossfade_duration = settings.CROSSFADE_DURATION_MS
        logger.info("audio_processor_initialized", crossfade_ms=self.crossfade_duration)

    def load_audio(self, audio_data: bytes, format: str = None) -> AudioSegment:
        """
        Load audio from bytes

        Args:
            audio_data: Audio bytes
            format: Audio format (opus, mp3, wav). Auto-detect if None.
        """
        try:
            format = format or settings.AUDIO_FORMAT

            # Handle OPUS (stored as OGG)
            if format == "opus":
                format = "ogg"

            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=format,
            )

            return audio

        except Exception as e:
            logger.error("audio_load_failed", error=str(e))
            raise

    def concatenate_with_crossfade(
        self, audio_clips: List[bytes], crossfade_ms: int = None
    ) -> bytes:
        """
        Concatenate multiple audio clips with crossfading

        Args:
            audio_clips: List of audio data as bytes
            crossfade_ms: Crossfade duration in milliseconds (10-50ms recommended)

        Returns:
            Concatenated audio as bytes
        """
        if not audio_clips:
            raise ValueError("No audio clips provided")

        if len(audio_clips) == 1:
            return audio_clips[0]

        crossfade_duration = crossfade_ms or self.crossfade_duration

        try:
            # Load first clip
            result = self.load_audio(audio_clips[0])

            # Concatenate remaining clips with crossfade
            for audio_data in audio_clips[1:]:
                next_clip = self.load_audio(audio_data)

                # Apply crossfade
                result = result.append(next_clip, crossfade=crossfade_duration)

            # Normalize audio levels
            result = normalize(result)

            # Export to bytes
            output = io.BytesIO()
            result.export(
                output,
                format=self._get_export_format(),
                bitrate=settings.AUDIO_BITRATE,
            )

            audio_bytes = output.getvalue()

            logger.info(
                "audio_concatenated",
                clip_count=len(audio_clips),
                crossfade_ms=crossfade_duration,
                output_size=len(audio_bytes),
            )

            return audio_bytes

        except Exception as e:
            logger.error("audio_concatenation_failed", error=str(e))
            raise

    def concatenate_simple(self, audio_clips: List[bytes]) -> bytes:
        """
        Simple concatenation without crossfading
        Faster but may have audible gaps
        """
        if not audio_clips:
            raise ValueError("No audio clips provided")

        if len(audio_clips) == 1:
            return audio_clips[0]

        try:
            # Load and concatenate
            result = self.load_audio(audio_clips[0])

            for audio_data in audio_clips[1:]:
                next_clip = self.load_audio(audio_data)
                result += next_clip  # Simple append

            # Export
            output = io.BytesIO()
            result.export(
                output,
                format=self._get_export_format(),
                bitrate=settings.AUDIO_BITRATE,
            )

            return output.getvalue()

        except Exception as e:
            logger.error("simple_concatenation_failed", error=str(e))
            raise

    def normalize_audio(self, audio_data: bytes) -> bytes:
        """
        Normalize audio levels for consistent volume
        """
        try:
            audio = self.load_audio(audio_data)
            normalized = normalize(audio)

            output = io.BytesIO()
            normalized.export(
                output,
                format=self._get_export_format(),
                bitrate=settings.AUDIO_BITRATE,
            )

            return output.getvalue()

        except Exception as e:
            logger.error("normalization_failed", error=str(e))
            raise

    def adjust_tempo_pitch(
        self, audio_data: bytes, tempo_factor: float = 1.0, pitch_semitones: int = 0
    ) -> bytes:
        """
        Adjust tempo and pitch for better matching at clip boundaries

        Args:
            audio_data: Input audio bytes
            tempo_factor: Speed multiplier (1.0 = normal, 1.2 = 20% faster)
            pitch_semitones: Pitch shift in semitones (0 = no change)
        """
        try:
            audio = self.load_audio(audio_data)

            # Adjust tempo (speed without changing pitch)
            if tempo_factor != 1.0:
                audio = audio.speedup(playback_speed=tempo_factor)

            # Note: Pitch shifting requires additional dependencies (pyrubberband)
            # For now, we'll skip pitch adjustment
            # In production, you'd use: audio = pyrubberband.pitch_shift(audio, pitch_semitones)

            output = io.BytesIO()
            audio.export(
                output,
                format=self._get_export_format(),
                bitrate=settings.AUDIO_BITRATE,
            )

            return output.getvalue()

        except Exception as e:
            logger.error("tempo_pitch_adjustment_failed", error=str(e))
            raise

    def convert_format(
        self, audio_data: bytes, input_format: str, output_format: str
    ) -> bytes:
        """
        Convert audio between formats

        Args:
            audio_data: Input audio bytes
            input_format: Source format (mp3, wav, opus)
            output_format: Target format (mp3, wav, opus)
        """
        try:
            audio = self.load_audio(audio_data, format=input_format)

            # Handle OPUS output (save as OGG)
            export_format = "ogg" if output_format == "opus" else output_format

            output = io.BytesIO()
            audio.export(output, format=export_format, bitrate=settings.AUDIO_BITRATE)

            logger.debug(
                "format_converted",
                from_format=input_format,
                to_format=output_format,
            )

            return output.getvalue()

        except Exception as e:
            logger.error("format_conversion_failed", error=str(e))
            raise

    def get_audio_duration(self, audio_data: bytes) -> float:
        """
        Get audio duration in seconds

        Args:
            audio_data: Audio bytes

        Returns:
            Duration in seconds
        """
        try:
            audio = self.load_audio(audio_data)
            return len(audio) / 1000.0  # Convert ms to seconds

        except Exception as e:
            logger.error("duration_calculation_failed", error=str(e))
            raise

    def _get_export_format(self) -> str:
        """Get export format for pydub"""
        if settings.AUDIO_FORMAT == "opus":
            return "ogg"
        return settings.AUDIO_FORMAT


# Global audio processor instance
audio_processor = AudioProcessor()
