from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.services.pipeline import process_video_pipeline
from backend.utils.video_utils import ensure_dir

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "uploads"
OUTPUT_DIR = ROOT / "data" / "outputs"
TEMPLATE_DIR = ROOT / "frontend" / "templates"
DATA_DIR = ROOT / "data"
ensure_dir(UPLOAD_DIR)
ensure_dir(OUTPUT_DIR)

ALLOWED_VIDEO_SUFFIXES = {
	".mp4",
	".mov",
	".mkv",
	".avi",
	".webm",
	".m4v",
	".wmv",
	".flv",
	".mpeg",
	".mpg",
	".3gp",
}

app = FastAPI(title="AttentionX API", version="1.0.0")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(DATA_DIR)), name="media")

JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}


def _public_url_for_file(file_path: str) -> str:
	path = Path(file_path)
	try:
		rel = path.resolve().relative_to(DATA_DIR.resolve())
	except Exception:
		return ""
	return f"/media/{rel.as_posix()}"


def _enrich_result(result: dict[str, Any]) -> dict[str, Any]:
	for clip in result.get("clips", []):
		clip["clip_url"] = _public_url_for_file(clip.get("clip_path", ""))
		clip["caption_url"] = _public_url_for_file(clip.get("caption_path", ""))
		clip["caption_vtt_url"] = _public_url_for_file(clip.get("caption_vtt_path", ""))
	return result


def _load_recent_jobs(limit: int) -> list[dict[str, Any]]:
	jobs: list[dict[str, Any]] = []
	if not OUTPUT_DIR.exists():
		return jobs

	result_files = sorted(
		OUTPUT_DIR.glob("*/result.json"),
		key=lambda item: item.stat().st_mtime,
		reverse=True,
	)

	for result_file in result_files[:limit]:
		try:
			payload = json.loads(result_file.read_text(encoding="utf-8"))
			payload = _enrich_result(payload)
			jobs.append(
				{
					"job_id": result_file.parent.name,
					"created": int(result_file.stat().st_mtime),
					"input_video": payload.get("input_video", ""),
					"clips": payload.get("clips", []),
				}
			)
		except Exception:
			continue

	return jobs


def _run_processing_job(
	job_id: str,
	input_path: Path,
	max_clips: int,
	language: str | None,
	clip_duration_seconds: float,
	analysis_start_seconds: float | None,
	analysis_end_seconds: float | None,
) -> None:
	try:
		result = process_video_pipeline(
			video_path=input_path,
			output_root=OUTPUT_DIR,
			max_clips=max(1, min(max_clips, 10)),
			language=language,
			clip_duration_seconds=clip_duration_seconds,
			analysis_start_seconds=analysis_start_seconds,
			analysis_end_seconds=analysis_end_seconds,
		)
		enriched = _enrich_result(result)
		with JOBS_LOCK:
			JOBS[job_id]["status"] = "completed"
			JOBS[job_id]["completed_at"] = int(time.time())
			JOBS[job_id]["result"] = enriched
	except Exception as exc:
		with JOBS_LOCK:
			JOBS[job_id]["status"] = "failed"
			JOBS[job_id]["completed_at"] = int(time.time())
			JOBS[job_id]["error"] = str(exc)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
	return templates.TemplateResponse(
		request=request,
		name="index.html",
		context={"app_name": "AttentionX"},
	)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok", "service": "attentionx-fastapi"}


@app.get("/jobs")
def recent_jobs(limit: int = 6) -> dict[str, Any]:
	max_limit = max(1, min(limit, 20))
	return {"jobs": _load_recent_jobs(max_limit)}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
	with JOBS_LOCK:
		job = JOBS.get(job_id)
	if job is None:
		raise HTTPException(status_code=404, detail="Job not found")

	response: dict[str, Any] = {
		"job_id": job_id,
		"status": job.get("status", "processing"),
		"created_at": job.get("created_at"),
	}
	if job.get("status") == "completed":
		response["result"] = job.get("result", {})
	if job.get("status") == "failed":
		response["error"] = job.get("error", "Processing failed")
	return response


@app.post("/process")
async def process_video(
	file: UploadFile = File(...),
	max_clips: int = Form(5),
	clip_duration_seconds: float = Form(8.0),
	analysis_start_seconds: float | None = Form(default=None),
	analysis_end_seconds: float | None = Form(default=None),
	language: str | None = Form(default=None),
) -> dict:
	if not file.filename:
		raise HTTPException(status_code=400, detail="Missing file name.")

	suffix = Path(file.filename).suffix.lower()
	if suffix not in ALLOWED_VIDEO_SUFFIXES:
		raise HTTPException(status_code=400, detail="Unsupported video format.")

	job_id = uuid.uuid4().hex
	safe_name = Path(file.filename).name
	input_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
	with input_path.open("wb") as out:
		out.write(await file.read())

	with JOBS_LOCK:
		JOBS[job_id] = {
			"status": "processing",
			"created_at": int(time.time()),
			"input_video": safe_name,
		}

	worker = threading.Thread(
		target=_run_processing_job,
		args=(
			job_id,
			input_path,
			max_clips,
			language,
			clip_duration_seconds,
			analysis_start_seconds,
			analysis_end_seconds,
		),
		daemon=True,
	)
	worker.start()

	return {
		"job_id": job_id,
		"status": "processing",
		"message": "Upload complete. Processing started.",
	}
