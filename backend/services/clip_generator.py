from __future__ import annotations

from bisect import bisect_left
from pathlib import Path

import numpy as np
from moviepy.editor import VideoFileClip

from backend.services.face_tracking import TrackingPoint


class ClipGenerator:
	"""Cuts source segments and applies dynamic 9:16 smart-crop."""

	def __init__(self, target_height: int = 1280) -> None:
		self.target_height = target_height

	def _safe_write(self, clip, output_path: Path) -> None:
		"""Write video with audio, then fall back to silent video if audio decode fails."""
		try:
			clip.write_videofile(
				str(output_path),
				codec="libx264",
				audio_codec="aac",
				preset="veryfast",
				threads=4,
				ffmpeg_params=["-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
				verbose=False,
				logger=None,
			)
		except Exception:
			clip.write_videofile(
				str(output_path),
				codec="libx264",
				audio=False,
				preset="veryfast",
				threads=4,
				ffmpeg_params=["-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
				verbose=False,
				logger=None,
			)

	def generate_vertical_clip(
		self,
		source_video: Path,
		output_path: Path,
		start: float,
		end: float,
		tracking_points: list[TrackingPoint],
	) -> None:
		output_path.parent.mkdir(parents=True, exist_ok=True)
		with VideoFileClip(str(source_video)) as video:
			duration = float(video.duration or 0.0)
			clip_start = max(0.0, min(start, duration))
			clip_end = max(clip_start + 1.0, min(end, duration))

			sub = video.subclip(clip_start, clip_end)
			width, height = sub.size
			target_width = int(height * (9 / 16))
			output_height = self.target_height

			if target_width >= width:
				# If source is already narrow, just resize to vertical friendly output.
				final = sub.resize(height=output_height)
				self._safe_write(final, output_path)
				return

			times = [p.time for p in tracking_points]
			centers = [p.x_center for p in tracking_points]

			def center_for_time(global_t: float) -> float:
				if not times:
					return 0.5
				idx = bisect_left(times, global_t)
				if idx <= 0:
					return centers[0]
				if idx >= len(times):
					return centers[-1]

				left_t, right_t = times[idx - 1], times[idx]
				left_x, right_x = centers[idx - 1], centers[idx]
				if right_t == left_t:
					return right_x
				alpha = (global_t - left_t) / (right_t - left_t)
				return float((1 - alpha) * left_x + alpha * right_x)

			def smart_crop(frame: np.ndarray, local_t: float) -> np.ndarray:
				global_t = clip_start + float(local_t)
				center_x_norm = center_for_time(global_t)
				center_x = int(center_x_norm * width)

				left = max(0, min(width - target_width, center_x - (target_width // 2)))
				right = left + target_width
				return frame[:, left:right]

			cropped = sub.fl(lambda gf, t: smart_crop(gf(t), t), apply_to=["mask"])
			final = cropped.resize(height=output_height)
			self._safe_write(final, output_path)
