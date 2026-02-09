"""
Transcription service — converts video/audio to timestamped text.

Uses AssemblyAI for:
- Speech-to-text transcription
- Speaker diarization (identifies different speakers)
- Punctuation and formatting

The output format matches what the coaching analysis engine expects:
    [HH:MM:SS] Speaker A: This is what they said...
    [HH:MM:SS] Speaker B: And this is the response...

Key concept: This service is SYNCHRONOUS (blocking). AssemblyAI's SDK
handles polling internally — it submits the audio, waits for processing,
and returns the result. That's why we run it in a background task, not
in the request handler (which would block the entire server).
"""

import time
from dataclasses import dataclass

import assemblyai as aai

from app.config import settings


@dataclass
class TranscriptionResult:
    """Structured output from transcription."""
    transcript_text: str      # Formatted with timestamps and speaker labels
    raw_text: str             # Plain text without formatting
    word_count: int
    speaker_count: int
    duration_seconds: int
    assemblyai_id: str
    processing_time_seconds: int


class TranscriptionService:
    """Wraps AssemblyAI's SDK for video/audio transcription.

    Usage:
        service = TranscriptionService()
        result = service.transcribe("https://example.com/video.mp4")
        print(result.transcript_text)  # Timestamped, speaker-labeled text
    """

    def __init__(self):
        aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
        self.transcriber = aai.Transcriber()

    def transcribe(self, audio_url: str) -> TranscriptionResult:
        """Transcribe audio/video from a URL.

        This is a BLOCKING call. AssemblyAI's SDK submits the file,
        polls for completion, and returns when done. For a 1-hour video,
        this takes roughly 15-45 minutes.

        Args:
            audio_url: Public URL to the audio/video file.
                      For local files, we'll need to upload first.

        Returns:
            TranscriptionResult with formatted transcript and metadata.

        Raises:
            Exception: If transcription fails (network error, bad audio, etc.)
        """
        start_time = time.time()

        config = aai.TranscriptionConfig(
            speaker_labels=True,   # Enable speaker diarization
            punctuate=True,        # Add punctuation
            format_text=True,      # Clean up formatting
        )

        # This blocks until transcription is complete
        transcript = self.transcriber.transcribe(audio_url, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            raise Exception(f"Transcription failed: {transcript.error}")

        processing_time = int(time.time() - start_time)

        # Format transcript with timestamps and speaker labels
        # PRD format: [HH:MM:SS] Speaker A: text content here
        formatted_lines = self._format_transcript(transcript)

        # Count unique speakers
        speakers = set()
        if transcript.utterances:
            speakers = {u.speaker for u in transcript.utterances}

        return TranscriptionResult(
            transcript_text="\n".join(formatted_lines),
            raw_text=transcript.text or "",
            word_count=len(transcript.words) if transcript.words else 0,
            speaker_count=len(speakers),
            duration_seconds=int((transcript.audio_duration or 0) / 1000),  # ms → sec
            assemblyai_id=transcript.id,
            processing_time_seconds=processing_time,
        )

    def _format_transcript(self, transcript) -> list[str]:
        """Format utterances into timestamped, speaker-labeled lines.

        Converts AssemblyAI's utterance format into:
            [00:00:05] Speaker A: Welcome everyone to today's session...
            [00:00:12] Speaker A: We're going to cover three main topics...
            [00:01:30] Speaker B: I have a question about the first topic...
        """
        formatted = []

        if not transcript.utterances:
            # Fallback: no speaker diarization available
            # Split raw text into chunks with estimated timestamps
            if transcript.text:
                formatted.append(f"[00:00:00] Speaker A: {transcript.text}")
            return formatted

        for utterance in transcript.utterances:
            # Convert milliseconds to HH:MM:SS
            start_ms = utterance.start
            total_seconds = start_ms // 1000
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            timestamp = f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
            speaker = f"Speaker {utterance.speaker}"
            text = utterance.text

            formatted.append(f"{timestamp} {speaker}: {text}")

        return formatted

    def transcribe_local_file(self, file_path: str) -> TranscriptionResult:
        """Transcribe a local file by uploading it to AssemblyAI first.

        AssemblyAI needs a URL to fetch the audio from. For local files,
        we upload to their servers first, get a temporary URL, then transcribe.

        Args:
            file_path: Path to local audio/video file.

        Returns:
            TranscriptionResult with formatted transcript.
        """
        start_time = time.time()

        config = aai.TranscriptionConfig(
            speaker_labels=True,
            punctuate=True,
            format_text=True,
        )

        # AssemblyAI's SDK handles local file upload automatically
        transcript = self.transcriber.transcribe(file_path, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            raise Exception(f"Transcription failed: {transcript.error}")

        processing_time = int(time.time() - start_time)
        formatted_lines = self._format_transcript(transcript)

        speakers = set()
        if transcript.utterances:
            speakers = {u.speaker for u in transcript.utterances}

        return TranscriptionResult(
            transcript_text="\n".join(formatted_lines),
            raw_text=transcript.text or "",
            word_count=len(transcript.words) if transcript.words else 0,
            speaker_count=len(speakers),
            duration_seconds=int((transcript.audio_duration or 0) / 1000),
            assemblyai_id=transcript.id,
            processing_time_seconds=processing_time,
        )
