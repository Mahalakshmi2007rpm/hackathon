from __future__ import annotations

import json
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

	input_path = UPLOAD_DIR / file.filename
	with input_path.open("wb") as out:
		out.write(await file.read())

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
		return _enrich_result(result)
	except Exception as exc:
		raise HTTPException(
			status_code=500,
			detail=f"Video processing failed: {exc}",
		) from exc
