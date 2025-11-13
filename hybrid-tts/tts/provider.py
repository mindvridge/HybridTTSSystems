"""
TTS Provider abstraction supporting Google Cloud TTS and Amazon Polly
"""
from abc import ABC, abstractmethod
from typing import Optional
import structlog
from config import settings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryCallState,
)
from google.api_core import exceptions as google_exceptions
from botocore.exceptions import (
    ClientError,
    BotoCoreError,
    ConnectionError as BotoConnectionError,
)

logger = structlog.get_logger()

# Import metrics for retry tracking
try:
    from api.routes.monitoring import (
        tts_retry_total,
        tts_retry_success_total,
        tts_retry_exhausted_total,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("metrics_not_available", message="TTS retry metrics not available")


def is_retryable_google_error(exception: Exception) -> bool:
    """Determine if a Google Cloud API error is retryable"""
    if isinstance(exception, google_exceptions.GoogleAPIError):
        # Retry on transient errors
        return isinstance(
            exception,
            (
                google_exceptions.ServiceUnavailable,
                google_exceptions.TooManyRequests,
                google_exceptions.InternalServerError,
                google_exceptions.BadGateway,
                google_exceptions.DeadlineExceeded,
            ),
        )
    # Retry on network errors
    return isinstance(exception, (ConnectionError, TimeoutError))


def is_retryable_polly_error(exception: Exception) -> bool:
    """Determine if an Amazon Polly error is retryable"""
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        # Retry on throttling and server errors
        return error_code in [
            "Throttling",
            "ThrottlingException",
            "ServiceUnavailable",
            "InternalError",
            "RequestTimeout",
        ]
    # Retry on connection errors
    return isinstance(exception, (BotoCoreError, BotoConnectionError, ConnectionError, TimeoutError))


def log_retry_attempt(retry_state: RetryCallState, provider: str):
    """Log and track retry attempts with metrics"""
    attempt_number = retry_state.attempt_number

    logger.warning(
        "tts_api_retry_attempt",
        provider=provider,
        attempt=attempt_number,
        exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
    )

    # Record retry metric
    if METRICS_AVAILABLE:
        tts_retry_total.labels(
            provider=provider,
            retry_attempt=str(attempt_number)
        ).inc()


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

    @retry(
        retry=retry_if_exception_type(
            lambda e: is_retryable_google_error(e)
        ),
        stop=stop_after_attempt(settings.TTS_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.TTS_RETRY_MULTIPLIER,
            min=settings.TTS_RETRY_INITIAL_WAIT_MS / 1000,
            max=settings.TTS_RETRY_MAX_WAIT_MS / 1000,
        ),
        before_sleep=lambda retry_state: log_retry_attempt(retry_state, "google"),
        reraise=True,
    )
    def _synthesize_with_retry(
        self,
        synthesis_input,
        voice_params,
        audio_config,
        text: str,
    ):
        """Internal method with retry logic for Google Cloud TTS API call"""
        logger.info(
            "google_tts_api_call_attempt",
            text_length=len(text),
        )

        # Perform synthesis with timeout
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
            timeout=settings.TTS_REQUEST_TIMEOUT_SEC,
        )

        return response

    async def synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> bytes:
        """
        Synthesize speech using Google Cloud TTS with automatic retry logic

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

            # Perform synthesis with retry logic
            response = self._synthesize_with_retry(
                synthesis_input,
                voice_params,
                audio_config,
                text,
            )

            logger.info(
                "tts_synthesized",
                provider="google",
                text_length=len(text),
                audio_size=len(response.audio_content),
            )

            # Record successful synthesis (possibly after retries)
            if METRICS_AVAILABLE:
                tts_retry_success_total.labels(provider="google").inc()

            return response.audio_content

        except Exception as e:
            logger.error(
                "google_tts_synthesis_failed",
                error=str(e),
                error_type=type(e).__name__,
                text=text[:50],
            )

            # Record exhausted retries
            if METRICS_AVAILABLE:
                tts_retry_exhausted_total.labels(
                    provider="google",
                    error_type=type(e).__name__
                ).inc()

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

    @retry(
        retry=retry_if_exception_type(
            lambda e: is_retryable_polly_error(e)
        ),
        stop=stop_after_attempt(settings.TTS_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.TTS_RETRY_MULTIPLIER,
            min=settings.TTS_RETRY_INITIAL_WAIT_MS / 1000,
            max=settings.TTS_RETRY_MAX_WAIT_MS / 1000,
        ),
        before_sleep=lambda retry_state: log_retry_attempt(retry_state, "polly"),
        reraise=True,
    )
    def _synthesize_with_retry(
        self,
        text: str,
        voice_id: str,
        output_format: str,
        engine: str,
    ):
        """Internal method with retry logic for Amazon Polly API call"""
        logger.info(
            "polly_api_call_attempt",
            text_length=len(text),
        )

        # Configure request with timeout
        config = {
            "Text": text,
            "VoiceId": voice_id,
            "OutputFormat": output_format,
            "Engine": engine,
            "SampleRate": str(settings.AUDIO_SAMPLE_RATE),
        }

        # Perform synthesis with configured timeout
        response = self.client.synthesize_speech(**config)

        return response

    async def synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> bytes:
        """
        Synthesize speech using Amazon Polly with automatic retry logic

        Args:
            text: Text to synthesize
            voice: Voice ID (e.g., 'Seoyeon', 'Joanna')
            **kwargs: Additional parameters (engine, language_code, etc.)
        """
        try:
            voice_id = voice or settings.POLLY_VOICE_ID
            engine = kwargs.get("engine", settings.POLLY_ENGINE)
            output_format = self._get_output_format()

            # Perform synthesis with retry logic
            response = self._synthesize_with_retry(
                text,
                voice_id,
                output_format,
                engine,
            )

            # Read audio stream
            audio_data = response["AudioStream"].read()

            logger.info(
                "tts_synthesized",
                provider="polly",
                text_length=len(text),
                audio_size=len(audio_data),
            )

            # Record successful synthesis (possibly after retries)
            if METRICS_AVAILABLE:
                tts_retry_success_total.labels(provider="polly").inc()

            return audio_data

        except Exception as e:
            logger.error(
                "polly_tts_synthesis_failed",
                error=str(e),
                error_type=type(e).__name__,
                text=text[:50],
            )

            # Record exhausted retries
            if METRICS_AVAILABLE:
                tts_retry_exhausted_total.labels(
                    provider="polly",
                    error_type=type(e).__name__
                ).inc()

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
