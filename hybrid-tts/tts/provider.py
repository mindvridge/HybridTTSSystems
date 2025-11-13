"""
TTS Provider abstraction supporting Google Cloud TTS and Amazon Polly
"""
from abc import ABC, abstractmethod
from typing import Optional
import structlog
from config import settings

logger = structlog.get_logger()


class TTSProvider(ABC):
    """Abstract base class for TTS providers"""

    @abstractmethod
    async def synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> bytes:
        """Synthesize text to audio bytes"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass


class GoogleCloudTTSProvider(TTSProvider):
    """Google Cloud Text-to-Speech provider"""

    def __init__(self):
        try:
            from google.cloud import texttospeech

            self.client = texttospeech.TextToSpeechClient()
            self.texttospeech = texttospeech
            logger.info("google_tts_initialized")
        except Exception as e:
            logger.error("google_tts_init_failed", error=str(e))
            raise

    async def synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> bytes:
        """
        Synthesize speech using Google Cloud TTS

        Args:
            text: Text to synthesize
            voice: Voice name (e.g., 'ko-KR-Neural2-A')
            **kwargs: Additional parameters (language_code, speaking_rate, pitch, etc.)
        """
        try:
            # Set up synthesis input
            synthesis_input = self.texttospeech.SynthesisInput(text=text)

            # Voice configuration
            voice_name = voice or settings.GOOGLE_TTS_VOICE
            language_code = kwargs.get("language_code", settings.GOOGLE_TTS_LANGUAGE)

            voice_params = self.texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )

            # Audio configuration
            audio_config = self.texttospeech.AudioConfig(
                audio_encoding=self._get_audio_encoding(),
                sample_rate_hertz=settings.AUDIO_SAMPLE_RATE,
                speaking_rate=kwargs.get("speaking_rate", 1.0),
                pitch=kwargs.get("pitch", 0.0),
            )

            # Perform synthesis
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )

            logger.info(
                "tts_synthesized",
                provider="google",
                text_length=len(text),
                audio_size=len(response.audio_content),
            )

            return response.audio_content

        except Exception as e:
            logger.error("google_tts_synthesis_failed", error=str(e), text=text[:50])
            raise

    def _get_audio_encoding(self):
        """Map config audio format to Google Cloud encoding"""
        format_map = {
            "mp3": self.texttospeech.AudioEncoding.MP3,
            "opus": self.texttospeech.AudioEncoding.OGG_OPUS,
            "wav": self.texttospeech.AudioEncoding.LINEAR16,
        }
        return format_map.get(
            settings.AUDIO_FORMAT, self.texttospeech.AudioEncoding.OGG_OPUS
        )

    def get_provider_name(self) -> str:
        return "google_cloud_tts"


class AmazonPollyProvider(TTSProvider):
    """Amazon Polly Text-to-Speech provider"""

    def __init__(self):
        try:
            import boto3

            self.client = boto3.client(
                "polly",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info("polly_tts_initialized")
        except Exception as e:
            logger.error("polly_tts_init_failed", error=str(e))
            raise

    async def synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> bytes:
        """
        Synthesize speech using Amazon Polly

        Args:
            text: Text to synthesize
            voice: Voice ID (e.g., 'Seoyeon', 'Joanna')
            **kwargs: Additional parameters (engine, language_code, etc.)
        """
        try:
            voice_id = voice or settings.POLLY_VOICE_ID
            engine = kwargs.get("engine", settings.POLLY_ENGINE)

            response = self.client.synthesize_speech(
                Text=text,
                VoiceId=voice_id,
                OutputFormat=self._get_output_format(),
                Engine=engine,
                SampleRate=str(settings.AUDIO_SAMPLE_RATE),
            )

            # Read audio stream
            audio_data = response["AudioStream"].read()

            logger.info(
                "tts_synthesized",
                provider="polly",
                text_length=len(text),
                audio_size=len(audio_data),
            )

            return audio_data

        except Exception as e:
            logger.error("polly_tts_synthesis_failed", error=str(e), text=text[:50])
            raise

    def _get_output_format(self) -> str:
        """Map config audio format to Polly output format"""
        format_map = {
            "mp3": "mp3",
            "opus": "ogg_vorbis",  # Polly uses Vorbis, not Opus
            "wav": "pcm",
        }
        return format_map.get(settings.AUDIO_FORMAT, "ogg_vorbis")

    def get_provider_name(self) -> str:
        return "amazon_polly"


def get_tts_provider() -> TTSProvider:
    """
    Factory function to get configured TTS provider
    Returns appropriate provider based on settings
    """
    provider_name = settings.TTS_PROVIDER.lower()

    if provider_name == "google":
        return GoogleCloudTTSProvider()
    elif provider_name == "polly":
        return AmazonPollyProvider()
    else:
        logger.error("unknown_tts_provider", provider=provider_name)
        raise ValueError(f"Unknown TTS provider: {provider_name}")


# Global provider instance
tts_provider = get_tts_provider()
