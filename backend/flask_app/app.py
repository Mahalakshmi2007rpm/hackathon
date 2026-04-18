from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

from backend.services.pipeline import process_video_pipeline
from backend.utils.video_utils import ensure_dir

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "uploads"
OUTPUT_DIR = ROOT / "data" / "outputs"
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

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[dict, int]:
	return {"status": "ok", "service": "attentionx-flask"}, 200


@app.post("/process")
def process_video() -> tuple[dict, int]:
	file = request.files.get("file")
	if file is None or not file.filename:
		return {"error": "Missing uploaded file."}, 400

	suffix = Path(file.filename).suffix.lower()
	if suffix not in ALLOWED_VIDEO_SUFFIXES:
		return {"error": "Unsupported video format."}, 400

	input_path = UPLOAD_DIR / file.filename
	file.save(str(input_path))

	max_clips = int(request.form.get("max_clips", 5))
	language = request.form.get("language")
	result = process_video_pipeline(
		video_path=input_path,
		output_root=OUTPUT_DIR,
		max_clips=max(1, min(max_clips, 10)),
		language=language,
	)
	return jsonify(result), 200


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=True)
