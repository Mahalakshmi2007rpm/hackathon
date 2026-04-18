from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from moviepy.editor import VideoFileClip

from backend.services.caption_generator import CaptionGenerator
from backend.services.clip_generator import ClipGenerator
from backend.services.emotion_detection import EmotionalPeakDetector, PeakCandidate
from backend.services.face_tracking import FaceTracker
from backend.services.transcription import WhisperTranscriber
from backend.utils.audio_utils import extract_audio_wav
from backend.utils.video_utils import ensure_dir, now_slug, save_json, slugify


def process_video_pipeline(
    video_path: Path,
    output_root: Path,
    max_clips: int = 5,
    language: str | None = None,
    clip_duration_seconds: float = 8.0,
    analysis_start_seconds: float | None = None,
    analysis_end_seconds: float | None = None,
) -> dict[str, Any]:
    """Run AttentionX core processing and return generated clip metadata."""
    ensure_dir(output_root)
    base_name = slugify(video_path.stem)
    job_dir = output_root / f"{now_slug()}-{base_name}"
    clips_dir = job_dir / "clips"
    captions_dir = job_dir / "captions"
    ensure_dir(job_dir)
    ensure_dir(clips_dir)
    ensure_dir(captions_dir)

    with VideoFileClip(str(video_path)) as video:
        full_duration = float(video.duration or 0.0)

    clip_duration_seconds = max(4.0, min(float(clip_duration_seconds), 20.0))
    analysis_start = max(0.0, float(analysis_start_seconds or 0.0))
    if analysis_start >= full_duration:
        analysis_start = 0.0
    if analysis_end_seconds is None:
        analysis_end = min(full_duration, analysis_start + 60.0)
    else:
        analysis_end = max(analysis_start + clip_duration_seconds, min(float(analysis_end_seconds), full_duration))
    if analysis_end <= analysis_start:
        analysis_start = 0.0
        analysis_end = min(full_duration, max(60.0, clip_duration_seconds))

    analysis_window_seconds = max(clip_duration_seconds, analysis_end - analysis_start)

    audio_path = extract_audio_wav(
        video_path,
        job_dir,
        start_seconds=analysis_start,
        max_seconds=analysis_window_seconds,
    )

    transcriber = WhisperTranscriber()
    transcript = transcriber.transcribe(
        video_path,
        language=language,
        audio_fallback_path=audio_path,
        offset_seconds=analysis_start,
    )

    detector = EmotionalPeakDetector()
    peaks = detector.detect(
        audio_path=audio_path,
        transcript=transcript,
        max_peaks=max_clips,
        clip_duration_seconds=clip_duration_seconds,
        window_start_seconds=analysis_start,
        window_end_seconds=analysis_end,
    )
    if len(peaks) < max_clips:
        # Defensive fill to guarantee the requested number of clips.
        step = analysis_window_seconds / float(max(max_clips, 1))
        for index in range(max_clips - len(peaks)):
            start = max(
                analysis_start,
                min(
                    analysis_start + (index + 0.5) * step,
                    max(analysis_start, analysis_end - clip_duration_seconds),
                ),
            )
            peaks.append(
                PeakCandidate(
                    start=round(start, 2),
                    end=round(min(analysis_end, start + clip_duration_seconds), 2),
                    score=0.05,
                    reason="Fallback: selected timing window",
                    hook="Key moment preview",
                )
            )
    peaks = peaks[:max_clips]

    tracker = FaceTracker()
    tracking = tracker.track(video_path, start_seconds=analysis_start, max_seconds=analysis_window_seconds)

    clipper = ClipGenerator()
    captioner = CaptionGenerator()

    clip_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, peak in enumerate(peaks, start=1):
        clip_raw_path = clips_dir / f"clip_{index:02d}_raw.mp4"
        clip_final_path = clips_dir / f"clip_{index:02d}.mp4"
        srt_path = captions_dir / f"clip_{index:02d}.srt"
        vtt_path = captions_dir / f"clip_{index:02d}.vtt"
        clip_start = max(analysis_start, min(peak.start, max(analysis_start, analysis_end - clip_duration_seconds)))
        clip_end = min(analysis_end, clip_start + clip_duration_seconds)

        try:
            clipper.generate_vertical_clip(
                source_video=video_path,
                output_path=clip_raw_path,
                start=clip_start,
                end=clip_end,
                tracking_points=tracking,
            )

            cues = captioner.build_cues_for_range(
                transcript=transcript,
                start=clip_start,
                end=clip_end,
            )
            captioner.write_srt(cues, srt_path)
            captioner.write_vtt(cues, vtt_path)

            captioner.burn_captions(
                source_video=clip_raw_path,
                srt_path=srt_path,
                output_video=clip_final_path,
                headline=peak.hook,
            )

            clip_results.append(
                {
                    "rank": index,
                    "score": peak.score,
                    "reason": peak.reason,
                    "start": clip_start,
                    "end": clip_end,
                    "duration": round(clip_end - clip_start, 2),
                    "hook": peak.hook,
                    "clip_path": str(clip_final_path),
                    "caption_path": str(srt_path),
                    "caption_vtt_path": str(vtt_path),
                }
            )
        except Exception as exc:
            warnings.append(f"Clip {index} failed: {exc}")

    result = {
        "input_video": str(video_path),
        "audio_path": str(audio_path),
        "job_dir": str(job_dir),
        "transcript": asdict(transcript),
        "peaks": [asdict(item) for item in peaks],
        "clips": clip_results,
        "warnings": warnings,
    }

    save_json(job_dir / "result.json", result)
    return result
