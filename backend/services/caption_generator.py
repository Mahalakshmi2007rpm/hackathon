from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path

from backend.services.transcription import Transcript


@dataclass
class CaptionCue:
	start: float
	end: float
	text: str


class CaptionGenerator:
	"""Creates timed captions and burns visual headline + subtitles into clip."""

	def build_cues_for_range(self, transcript: Transcript, start: float, end: float) -> list[CaptionCue]:
		cues: list[CaptionCue] = []
		for segment in transcript.segments:
			if segment.end < start or segment.start > end:
				continue
			cue_start = max(start, segment.start) - start
			cue_end = min(end, segment.end) - start
			text = segment.text.strip()
			if text and cue_end > cue_start:
				cues.append(CaptionCue(start=cue_start, end=cue_end, text=text))
		return cues

	def write_srt(self, cues: list[CaptionCue], output_path: Path) -> None:
		lines: list[str] = []
		for idx, cue in enumerate(cues, start=1):
			lines.append(str(idx))
			lines.append(f"{self._format_ts(cue.start)} --> {self._format_ts(cue.end)}")
			lines.append(cue.text)
			lines.append("")

		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text("\n".join(lines), encoding="utf-8")

	def write_vtt(self, cues: list[CaptionCue], output_path: Path) -> None:
		lines: list[str] = ["WEBVTT", ""]
		for cue in cues:
			lines.append(f"{self._format_vtt_ts(cue.start)} --> {self._format_vtt_ts(cue.end)}")
			lines.append(cue.text)
			lines.append("")

		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text("\n".join(lines), encoding="utf-8")

	def burn_captions(self, source_video: Path, srt_path: Path, output_video: Path, headline: str) -> None:
		try:
			ffmpeg = shutil.which("ffmpeg")
			if ffmpeg is None:
				raise RuntimeError("ffmpeg is not available")

			headline = headline.strip() or "Watch this moment"
			subtitles_path = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
			font_file = Path("C:/Windows/Fonts/arialbd.ttf")
			if not font_file.exists():
				font_file = Path("C:/Windows/Fonts/Arial Bold.ttf")
			font_path = str(font_file).replace("\\", "/").replace(":", "\\:")

			drawtext_filter = (
				f"drawtext=fontfile='{font_path}':text='{self._escape_drawtext(headline)}':"
				"x=(w-text_w)/2:y=h*0.06:fontsize=48:fontcolor=white:box=1:boxcolor=black@0.45:"
				f"boxborderw=14:enable='lt(t,3.5)'"
			)
			filter_chain = (
				f"subtitles='{subtitles_path}':force_style='FontName=Arial,FontSize=28,"
				f"PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BackColour=&H80000000,"
				f"Outline=3,Alignment=2,MarginV=120',{drawtext_filter}"
			)

			cmd = [
				ffmpeg,
				"-y",
				"-i",
				str(source_video),
				"-vf",
				filter_chain,
				"-c:v",
				"libx264",
				"-preset",
				"veryfast",
				"-crf",
				"28",
				"-pix_fmt",
				"yuv420p",
				"-movflags",
				"+faststart",
				"-c:a",
				"aac",
				"-b:a",
				"96k",
				str(output_video),
			]
			result = subprocess.run(cmd, capture_output=True, text=True)
			if result.returncode != 0:
				raise RuntimeError(result.stderr.strip() or "ffmpeg caption burn failed")
		except Exception:
			# Preserve a usable output even if subtitles cannot be burned.
			output_video.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(source_video, output_video)

	def _format_ts(self, total_seconds: float) -> str:
		ms = int((total_seconds % 1) * 1000)
		total_int = int(total_seconds)
		seconds = total_int % 60
		minutes = (total_int // 60) % 60
		hours = total_int // 3600
		return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

	def _format_vtt_ts(self, total_seconds: float) -> str:
		ms = int((total_seconds % 1) * 1000)
		total_int = int(total_seconds)
		seconds = total_int % 60
		minutes = (total_int // 60) % 60
		hours = total_int // 3600
		return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"

	def _read_srt(self, srt_path: Path) -> list[CaptionCue]:
		content = srt_path.read_text(encoding="utf-8").strip()
		if not content:
			return []

		blocks = [block for block in content.split("\n\n") if block.strip()]
		cues: list[CaptionCue] = []
		for block in blocks:
			lines = block.splitlines()
			if len(lines) < 3:
				continue
			timeline = lines[1]
			text = " ".join(lines[2:]).strip()
			start_str, end_str = [item.strip() for item in timeline.split("-->")]
			cues.append(CaptionCue(start=self._parse_ts(start_str), end=self._parse_ts(end_str), text=text))
		return cues

	def _parse_ts(self, value: str) -> float:
		hh_mm_ss, ms = value.split(",")
		hh, mm, ss = hh_mm_ss.split(":")
		return (int(hh) * 3600) + (int(mm) * 60) + int(ss) + (int(ms) / 1000.0)

	def _escape_drawtext(self, text: str) -> str:
		return (
			text.replace("\\", "\\\\")
			.replace(":", r"\:")
			.replace("'", r"\'")
			.replace("%", r"\%")
			.replace("\n", " ")
		)
