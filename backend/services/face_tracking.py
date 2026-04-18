from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


@dataclass
class TrackingPoint:
	time: float
	x_center: float


class FaceTracker:
	"""Extracts normalized horizontal face center positions over time."""

	def __init__(self) -> None:
		self.face_detection = mp.solutions.face_detection.FaceDetection(
			model_selection=1,
			min_detection_confidence=0.5,
		)

	def track(
		self,
		video_path: Path,
		sample_every_n_frames: int = 20,
		start_seconds: float = 0.0,
		max_seconds: float | None = None,
	) -> list[TrackingPoint]:
		cap = cv2.VideoCapture(str(video_path))
		fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
		start_seconds = max(0.0, float(start_seconds))
		if start_seconds > 0:
			cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000.0)
		frame_index = 0

		points: list[TrackingPoint] = []
		try:
			while cap.isOpened():
				ok, frame = cap.read()
				if not ok:
					break

				if max_seconds is not None and (frame_index / fps) > max_seconds:
					break

				if frame_index % sample_every_n_frames != 0:
					frame_index += 1
					continue

				rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
				result = self.face_detection.process(rgb)
				if result.detections:
					detection = result.detections[0]
					bbox = detection.location_data.relative_bounding_box
					x_center = float(np.clip(bbox.xmin + (bbox.width / 2.0), 0.0, 1.0))
					t = start_seconds + (frame_index / fps)
					points.append(TrackingPoint(time=round(t, 3), x_center=x_center))

				frame_index += 1
		finally:
			cap.release()

		return self._smooth(points)

	def _smooth(self, points: list[TrackingPoint], window: int = 5) -> list[TrackingPoint]:
		if not points:
			return []

		values = np.array([p.x_center for p in points], dtype=np.float32)
		kernel = np.ones(window, dtype=np.float32) / float(window)
		smoothed = np.convolve(values, kernel, mode="same")

		return [
			TrackingPoint(time=points[i].time, x_center=float(np.clip(smoothed[i], 0.0, 1.0)))
			for i in range(len(points))
		]
