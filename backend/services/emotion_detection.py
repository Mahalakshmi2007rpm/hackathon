from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np

from backend.services.transcription import Transcript

try:
	import google.generativeai as genai
except Exception:  # pragma: no cover
	genai = None


POSITIVE_WORDS = {
	"breakthrough",
	"incredible",
	"powerful",
	"amazing",
	"important",
	"secret",
	"win",
	"growth",
	"success",
	"focus",
	"transform",
}

NEGATIVE_WORDS = {
	"problem",
	"mistake",
	"hard",
	"fail",
	"fear",
	"struggle",
	"pain",
	"stuck",
	"doubt",
}


@dataclass
class PeakCandidate:
	start: float
	end: float
	score: float
	reason: str
	hook: str


class EmotionalPeakDetector:
	"""Ranks candidate moments using acoustic intensity + sentiment cues."""

	def __init__(self) -> None:
		self.gemini_key = os.getenv("GEMINI_API_KEY")
		if self.gemini_key and genai is not None:
			genai.configure(api_key=self.gemini_key)
			self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
		else:
			self.gemini_model = None

	def detect(
		self,
		audio_path: Path,
		transcript: Transcript,
		max_peaks: int = 5,
		clip_duration_seconds: float = 8.0,
		window_start_seconds: float = 0.0,
		window_end_seconds: float | None = None,
	) -> list[PeakCandidate]:
		return self._detect_fixed_windows(
			audio_path,
			transcript,
			max_peaks=max_peaks,
			clip_duration_seconds=clip_duration_seconds,
			window_start_seconds=window_start_seconds,
			window_end_seconds=window_end_seconds,
		)

	def _detect_fixed_windows(
		self,
		audio_path: Path,
		transcript: Transcript,
		max_peaks: int,
		clip_duration_seconds: float,
		window_start_seconds: float = 0.0,
		window_end_seconds: float | None = None,
	) -> list[PeakCandidate]:
		signal, sample_rate = librosa.load(str(audio_path), sr=12000)
		if signal.size == 0:
			return []

		frame_length = 2048
		hop_length = 512
		rms = librosa.feature.rms(y=signal, frame_length=frame_length, hop_length=hop_length)[0]
		times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=hop_length)
		total_duration = float(librosa.get_duration(y=signal, sr=sample_rate)) or 0.0
		if total_duration <= 0:
			return self._fallback_candidates(transcript, max_peaks, total_duration, clip_duration_seconds)

		window_start_seconds = max(0.0, float(window_start_seconds))
		if window_end_seconds is None:
			window_end_seconds = total_duration
		else:
			window_end_seconds = max(window_start_seconds, min(float(window_end_seconds), total_duration))
		window_end_seconds = max(window_start_seconds, window_end_seconds)
		window_duration = max(0.0, window_end_seconds - window_start_seconds)
		if window_duration <= 0:
			window_start_seconds = 0.0
			window_end_seconds = total_duration
			window_duration = total_duration

		if len(rms) < 3:
			return self._fallback_candidates(transcript, max_peaks, total_duration, clip_duration_seconds)

		loud_threshold = float(np.percentile(rms, 90))
		peak_indexes = np.where(rms >= loud_threshold)[0]
		if peak_indexes.size == 0:
			return self._fallback_candidates(transcript, max_peaks, total_duration, clip_duration_seconds)

		clip_duration_seconds = max(4.0, min(float(clip_duration_seconds), 20.0))
		window_indexes = peak_indexes[:: max(1, len(peak_indexes) // (max_peaks * 2))]
		candidate_centers: list[float] = []

		for idx in window_indexes:
			candidate_centers.append(float(times[idx]))

		if len(candidate_centers) < max_peaks:
			step = total_duration / float(max(max_peaks, 1))
			for i in range(max_peaks * 2):
				candidate_centers.append((i + 0.5) * step)

		candidates: list[PeakCandidate] = []
		for center_t in candidate_centers:
			start = max(
				window_start_seconds,
				min(center_t - (clip_duration_seconds / 2), max(window_start_seconds, window_end_seconds - clip_duration_seconds)),
			)
			end = min(total_duration, start + clip_duration_seconds)
			if end > window_end_seconds:
				end = window_end_seconds
			if end <= start:
				continue

			frame_start = int((start / total_duration) * max(len(rms) - 1, 1))
			frame_end = int((end / total_duration) * max(len(rms) - 1, 1))
			frame_end = max(frame_end, frame_start + 1)
			window_rms = rms[frame_start:frame_end]
			loudness = float(np.mean(window_rms)) if window_rms.size else float(np.mean(rms))
			text = self._collect_text(transcript, start, end)
			sentiment = self._sentiment_score(text)
			score = (0.65 * loudness) + (0.35 * sentiment)
			reason = f"Audio energy={loudness:.3f}, sentiment={sentiment:.3f}"
			hook = self._generate_hook(text)

			candidates.append(
				PeakCandidate(
					start=round(start, 2),
					end=round(end, 2),
					score=round(score, 4),
					reason=reason,
					hook=hook,
				)
			)

		candidates.sort(key=lambda c: c.score, reverse=True)
		deduped = self._remove_overlaps(candidates)
		if len(deduped) < max_peaks:
			fallbacks = self._fallback_candidates(
				transcript,
				max_peaks,
				total_duration,
				clip_duration_seconds,
				window_start_seconds=window_start_seconds,
				window_end_seconds=window_end_seconds,
			)
			for candidate in fallbacks:
				if len(deduped) >= max_peaks:
					break
				if all(abs(candidate.start - existing.start) > 1.0 for existing in deduped):
					deduped.append(candidate)
		return deduped[:max_peaks]

	def _collect_text(self, transcript: Transcript, start: float, end: float) -> str:
		snippets = [
			segment.text
			for segment in transcript.segments
			if not (segment.end < start or segment.start > end)
		]
		return " ".join(snippets).strip()

	def _sentiment_score(self, text: str) -> float:
		if not text:
			return 0.0
		words = [token.strip(".,!?;:\"'()[]{}") for token in text.lower().split()]
		if not words:
			return 0.0

		pos = sum(1 for w in words if w in POSITIVE_WORDS)
		neg = sum(1 for w in words if w in NEGATIVE_WORDS)
		norm = max(len(words), 1)
		return (pos - neg) / norm

	def _generate_hook(self, text: str) -> str:
		if not text:
			return "Watch this key moment"

		fallback = " ".join(text.split()[:10]).strip()
		if fallback:
			fallback = f"{fallback}..."
		else:
			fallback = "Watch this key moment"

		if self.gemini_model is None:
			return fallback

		try:
			prompt = (
				"Create one short viral-style headline (max 9 words) from this transcript excerpt. "
				"Return plain text only.\n\n"
				f"Excerpt: {text}"
			)
			response = self.gemini_model.generate_content(prompt)
			hook = str(getattr(response, "text", "")).strip()
			return hook or fallback
		except Exception:
			return fallback

	def _remove_overlaps(self, candidates: list[PeakCandidate]) -> list[PeakCandidate]:
		selected: list[PeakCandidate] = []
		for candidate in candidates:
			has_overlap = any(
				not (candidate.end <= existing.start or candidate.start >= existing.end)
				for existing in selected
			)
			if not has_overlap:
				selected.append(candidate)
		return selected

	def _fallback_candidates(
		self,
		transcript: Transcript,
		max_peaks: int,
		total_duration: float,
		clip_duration_seconds: float,
		window_start_seconds: float = 0.0,
		window_end_seconds: float | None = None,
	) -> list[PeakCandidate]:
		candidates: list[PeakCandidate] = []
		window_start_seconds = max(0.0, float(window_start_seconds))
		window_end_seconds = total_duration if window_end_seconds is None else max(window_start_seconds, min(float(window_end_seconds), total_duration))
		if transcript.segments:
			for segment in transcript.segments[:max_peaks]:
				start = max(window_start_seconds, min(segment.start, max(window_start_seconds, window_end_seconds - clip_duration_seconds)))
				end = min(total_duration, start + clip_duration_seconds)
				if end > window_end_seconds:
					end = window_end_seconds
				candidates.append(
					PeakCandidate(
						start=round(start, 2),
						end=round(end, 2),
						score=0.1,
						reason="Fallback: insufficient audio peak signal",
						hook=self._generate_hook(segment.text),
					)
				)

		if len(candidates) < max_peaks and total_duration > 0:
			step = max(window_end_seconds - window_start_seconds, 0.0) / float(max(max_peaks, 1))
			for i in range(max_peaks):
				start = max(window_start_seconds, min(window_start_seconds + i * step, max(window_start_seconds, window_end_seconds - clip_duration_seconds)))
				end = min(total_duration, start + clip_duration_seconds)
				if end > window_end_seconds:
					end = window_end_seconds
				candidates.append(
					PeakCandidate(
						start=round(start, 2),
						end=round(end, 2),
						score=0.05,
						reason="Fallback: evenly spaced preview window",
						hook="Key moment preview",
					)
				)
		return candidates[:max_peaks]
