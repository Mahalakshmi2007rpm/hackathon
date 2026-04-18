from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

from moviepy.editor import VideoFileClip

try:
	from faster_whisper import WhisperModel
except Exception:  # pragma: no cover
	WhisperModel = None

try:
	import whisper as openai_whisper
except Exception:  # pragma: no cover
	openai_whisper = None

try:
	from openai import OpenAI
except Exception:  # pragma: no cover
	OpenAI = None


@dataclass
class TranscriptSegment:
	start: float
	end: float
	text: str


@dataclass
class Transcript:
	language: str
	text: str
	segments: list[TranscriptSegment]


class WhisperTranscriber:
	"""Converts video audio into timestamped transcript using Whisper API."""

	def __init__(self) -> None:
		self.api_key = os.getenv("OPENAI_API_KEY")
		self.client = OpenAI(api_key=self.api_key) if self.api_key and OpenAI is not None else None
		self.local_model_name = os.getenv("WHISPER_MODEL_SIZE", "tiny.en")
		self.local_model: WhisperModel | None = None
		self.openai_local_model = None

	def transcribe(
		self,
		video_path: Path,
		language: str | None = None,
		audio_fallback_path: Path | None = None,
		offset_seconds: float = 0.0,
	) -> Transcript:
		if self.client is not None:
			remote = self._transcribe_openai(
				video_path,
				language=language,
				audio_fallback_path=audio_fallback_path,
				offset_seconds=offset_seconds,
			)
			if remote is not None:
				return remote

		local = self._transcribe_local(
			audio_fallback_path if audio_fallback_path and audio_fallback_path.exists() else video_path,
			language=language,
			offset_seconds=offset_seconds,
		)
		if local is not None:
			return local

		return self._fallback_transcript(video_path)

	def _transcribe_openai(
		self,
		video_path: Path,
		language: str | None = None,
		audio_fallback_path: Path | None = None,
		offset_seconds: float = 0.0,
	) -> Transcript | None:
		if self.client is None:
			return None

		target_audio = audio_fallback_path if audio_fallback_path and audio_fallback_path.exists() else video_path
		with target_audio.open("rb") as audio_file:
			try:
				response = self.client.audio.transcriptions.create(
					model="whisper-1",
					file=audio_file,
					response_format="verbose_json",
					language=language,
					timestamp_granularities=["segment"],
				)
			except Exception:
				return None

		segments_raw = getattr(response, "segments", []) or []
		if not segments_raw:
			return self._fallback_transcript(video_path)

		segments: list[TranscriptSegment] = []
		for item in segments_raw:
			segments.append(
				TranscriptSegment(
					start=float(getattr(item, "start", 0.0)) + float(offset_seconds),
					end=float(getattr(item, "end", 0.0)) + float(offset_seconds),
					text=str(getattr(item, "text", "")).strip(),
				)
			)

		full_text = " ".join(segment.text for segment in segments).strip()
		return Transcript(
			language=str(getattr(response, "language", language or "unknown")),
			text=full_text,
			segments=segments,
		)

	def _transcribe_local(self, audio_path: Path, language: str | None = None, offset_seconds: float = 0.0) -> Transcript | None:
		fast_whisper_result = self._transcribe_local_faster_whisper(audio_path, language=language, offset_seconds=offset_seconds)
		if fast_whisper_result is not None:
			return fast_whisper_result

		return self._transcribe_local_openai_whisper(audio_path, language=language, offset_seconds=offset_seconds)

	def _transcribe_local_faster_whisper(self, audio_path: Path, language: str | None = None, offset_seconds: float = 0.0) -> Transcript | None:
		if WhisperModel is None:
			return None

		if self.local_model is None:
			try:
				self.local_model = WhisperModel(self.local_model_name, device="cpu", compute_type="int8")
			except Exception:
				logger.exception("faster-whisper model initialization failed")
				return None

		try:
			segments_iter, info = self.local_model.transcribe(
				str(audio_path),
				language=language,
				beam_size=1,
				vad_filter=True,
				word_timestamps=False,
			)
		except Exception:
			logger.exception("faster-whisper transcription failed")
			return None

		segments: list[TranscriptSegment] = []
		for item in segments_iter:
			text = str(getattr(item, "text", "")).strip()
			if not text:
				continue
			segments.append(
				TranscriptSegment(
					start=float(getattr(item, "start", 0.0)) + float(offset_seconds),
					end=float(getattr(item, "end", 0.0)) + float(offset_seconds),
					text=text,
				)
			)

		if not segments:
			return None

		full_text = " ".join(segment.text for segment in segments).strip()
		return Transcript(
			language=str(getattr(info, "language", language or "unknown")),
			text=full_text,
			segments=segments,
		)

	def _transcribe_local_openai_whisper(self, audio_path: Path, language: str | None = None, offset_seconds: float = 0.0) -> Transcript | None:
		if openai_whisper is None:
			return None

		try:
			if self.openai_local_model is None:
				self.openai_local_model = openai_whisper.load_model(self.local_model_name)
			result = self.openai_local_model.transcribe(str(audio_path), language=language, fp16=False)
		except Exception:
			logger.exception("openai-whisper transcription failed")
			return None

		segments_raw = result.get("segments", []) or []
		segments: list[TranscriptSegment] = []
		for item in segments_raw:
			text = str(item.get("text", "")).strip()
			if not text:
				continue
			segments.append(
				TranscriptSegment(
					start=float(item.get("start", 0.0)) + float(offset_seconds),
					end=float(item.get("end", 0.0)) + float(offset_seconds),
					text=text,
				)
			)

		if not segments:
			return None

		full_text = " ".join(segment.text for segment in segments).strip()
		return Transcript(
			language=str(result.get("language", language or "unknown")),
			text=full_text,
			segments=segments,
		)

	def _fallback_transcript(self, video_path: Path) -> Transcript:
		with VideoFileClip(str(video_path)) as video:
			duration = float(video.duration or 0.0)

		duration = max(duration, 1.0)
		segment = TranscriptSegment(
			start=0.0,
			end=duration,
			text="Automatic transcription unavailable. Please check Whisper model setup.",
		)
		return Transcript(language="unknown", text=segment.text, segments=[segment])
