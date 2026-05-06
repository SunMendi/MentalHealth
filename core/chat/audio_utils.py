import logging
import wave

logger = logging.getLogger("chat.audio")


def get_audio_duration_seconds(audio_file_path):
    try:
        with wave.open(audio_file_path, "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            if frame_rate:
                return float(frame_count) / float(frame_rate)
    except wave.Error:
        pass
    except Exception:
        logger.exception("Failed to inspect WAV duration for %s", audio_file_path)
        return None

    try:
        from mutagen import File as MutagenFile
    except ImportError:
        logger.exception("mutagen is not installed, cannot validate audio duration")
        return None

    try:
        parsed_file = MutagenFile(audio_file_path)
        if not parsed_file or not getattr(parsed_file, "info", None):
            logger.warning("Unsupported audio file for duration detection: %s", audio_file_path)
            return None

        duration = getattr(parsed_file.info, "length", None)
        if duration is None:
            logger.warning("Audio metadata missing duration: %s", audio_file_path)
            return None

        return float(duration)
    except Exception:
        logger.exception("Failed to inspect audio duration for %s", audio_file_path)
        return None
