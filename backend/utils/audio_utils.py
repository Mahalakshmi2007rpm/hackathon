from __future__ import annotations

from pathlib import Path

from moviepy.editor import VideoFileClip


def extract_audio_wav(
	video_path: Path,
	output_dir: Path,
	start_seconds: float = 0.0,
	max_seconds: float | None = None,
) -> Path:
	output_dir.mkdir(parents=True, exist_ok=True)
	audio_path = output_dir / "audio.wav"

	with VideoFileClip(str(video_path)) as video:
		if video.audio is None:
			raise ValueError("Input video has no audio track.")
		start_seconds = max(0.0, float(start_seconds))
		if max_seconds is not None:
			source = video.subclip(start_seconds, start_seconds + max_seconds)
		elif start_seconds > 0:
			source = video.subclip(start_seconds)
		else:
			source = video
		source.audio.write_audiofile(
			str(audio_path),
			fps=8000,
			codec="pcm_s16le",
			verbose=False,
			logger=None,
		)

	return audio_path
