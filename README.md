# AttentionX

AttentionX is an automated content repurposing engine that converts long-form mentorship videos into multiple short, vertical, captioned social clips.

It solves:
- Finding high-impact moments from long footage
- Converting 16:9 to 9:16 while keeping the speaker centered
- Generating timed captions and hook headlines for short-form engagement

## Core Features

1. Emotional Peak Detection
- Audio intensity scoring with Librosa
- Transcript sentiment cue scoring
- Optional Gemini 1.5 Flash hook enhancement

2. Smart Vertical Crop (9:16)
- Face tracking with MediaPipe
- Dynamic center crop around speaker position

3. Dynamic Captions
- Timestamped cues from Whisper transcript
- SRT generation
- Headline + subtitle overlay render

4. Dual Backend Support
- FastAPI (production style)
- Flask (hackathon prototype style)

5. Frontend
- Integrated FastAPI web app with compact reel cards
- Reel duration and source-window timing controls
- Pico.css landing page template

## Tech Stack

- AI and Multimodal APIs: OpenAI Whisper, Google Gemini 1.5 Flash (optional enhancement)
- Video/Audio: MoviePy, Librosa, MediaPipe, OpenCV
- Backend: FastAPI + Flask
- Frontend: Streamlit + Pico.css

## Project Structure

```
attentionx/
├── backend/
│   ├── fastapi_app/main.py
│   ├── flask_app/app.py
│   ├── services/
│   │   ├── transcription.py
│   │   ├── emotion_detection.py
│   │   ├── clip_generator.py
│   │   ├── face_tracking.py
│   │   ├── caption_generator.py
│   │   └── pipeline.py
│   └── utils/
│       ├── video_utils.py
│       └── audio_utils.py
├── frontend/
│   ├── streamlit_app.py
│   └── templates/index.html
├── data/
│   ├── uploads/
│   └── outputs/
├── requirements.txt
└── README.md
```

## Step-by-Step Build from Scratch

### 1) Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Configure environment variables

Set API keys in current shell:

```powershell
$env:OPENAI_API_KEY="your_openai_key"
$env:GEMINI_API_KEY="your_gemini_key"
```

Notes:
- OPENAI_API_KEY enables Whisper transcription.
- GEMINI_API_KEY is optional and improves hook headline quality.

### 4) Run FastAPI backend

```powershell
uvicorn backend.fastapi_app.main:app --host 0.0.0.0 --port 8000
```

Tip:
- Use `--reload` only while editing code. For long video processing tests, run without reload to avoid transient reconnect/network interruptions.

Test docs:
- http://127.0.0.1:8000/docs

Open the full web app:
- http://127.0.0.1:8000/

### 5) (Optional) Run Streamlit frontend

Open a second terminal:

```powershell
streamlit run frontend/streamlit_app.py
```

Open:
- http://127.0.0.1:8501

### 6) (Optional) Run Flask backend

```powershell
python backend/flask_app/app.py
```

Flask API URL:
- http://127.0.0.1:5000

## How Processing Works

1. User uploads long-form video.
2. Audio extracted to WAV.
3. Whisper transcribes with timestamp segments.
4. Emotional peaks selected using loudness spikes + sentiment.
5. Face tracker extracts speaker horizontal position over time.
6. Candidate moments are clipped and smart-cropped to vertical.
7. Caption cues are generated and burned into clips.
8. Final outputs saved in `data/outputs/<job-id>/`.

## API Contract (FastAPI)

### GET `/`

Serves the full AttentionX web application (upload UI + result cards + playable generated clips).

### GET `/media/*`

Serves generated files from the `data/` directory so clips and caption files can be viewed/downloaded in browser.

### GET `/jobs`

Returns recent processed jobs (latest first) with clip URLs for gallery previews in the web app.

### POST `/process`

Form-data:
- `file`: video file (.mp4, .mov, .mkv, .avi, .webm)
- `max_clips`: int (1-10)
- `clip_duration_seconds`: optional reel length per clip in seconds
- `analysis_start_seconds`: optional start of the source timing window
- `analysis_end_seconds`: optional end of the source timing window
- `language`: optional language hint

Response includes:
- transcript
- ranked peaks with hooks and reasons
- generated clip file paths and caption file paths

## Web App UX Highlights

- Drag-and-drop upload zone with file preview
- Upload progress bar
- Live processing timeline stages
- Top moments result cards with inline video playback
- Recent jobs gallery loaded from `/jobs`

## Fast Preview Output Mode

- The app now uses a short preview analysis window to keep turnaround fast.
- You can optionally focus processing on a source-video time range and choose the reel length per clip.
- Output clips are standardized to a neat vertical social format.
- The requested clip count is returned as closely as possible, with fallback windows if a peak is not found.
- Hook captions and timed subtitles are burned into the final clips when ffmpeg is available.

### GET `/health`

Returns service status.

## Quality and Accuracy Strategy

To maximize evaluation score:

1. Improve emotional ranking
- Add semantic scoring from Gemini on transcript chunks.
- Combine normalized features: loudness, speaking rate, sentiment polarity, keyword novelty.

2. Improve crop stability
- Use face landmarks and Kalman smoothing.
- Add fallback to body tracking when face is temporarily lost.

3. Improve captions
- Use word-level timestamps and karaoke highlighting.
- Add punctuation restoration and short line wrapping.

4. Improve reliability
- Add retry + timeout policy for external APIs.
- Add async job queue (Celery/RQ) for long videos.

## Hosting Guide (Publicly Accessible)

### Option A: Render Docker Web Service

1. Push the repo to GitHub.
2. In Render, create a new Web Service from the repo.
3. Choose the Docker runtime so Render uses the included `Dockerfile`.
4. Add environment variables as needed:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
5. Deploy. The service health check is available at `/health`.


 THIS IS THE WEBSITE URL WHICH WAS HOSTED IN THE RENDER : 
 URL : https://hackathon-eo4e.onrender.com/

PRESENTATION DEMO LINK : 
https://drive.google.com/file/d/1pbmztZZuOJWs-f3os8-tDi6DLyrSVwcu/view?usp=sharing
   

## Hackathon Submission Checklist

- Public GitHub repository
- Full source code present
- README with setup + architecture + usage
- Demo video link in README (mandatory)
- Hosted URL (optional bonus)

Add your demo section in this README:

```markdown
## Demo Video
Google Drive Link: <paste-link-here>

## Live Deployment
Frontend URL: <paste-streamlit-url>
Backend URL: <paste-api-url>
```

## Quick Start Commands

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OPENAI_API_KEY="your_openai_key"
$env:GEMINI_API_KEY="your_gemini_key"
uvicorn backend.fastapi_app.main:app --host 0.0.0.0 --port 8000 --reload
```

To run the Docker image locally:

```powershell
docker build -t attentionx .
docker run -p 8000:10000 -e OPENAI_API_KEY="your_openai_key" -e GEMINI_API_KEY="your_gemini_key" attentionx
```

In another terminal:

```powershell
streamlit run frontend/streamlit_app.py
```

## Important Notes

- Long videos are compute-heavy; start with short samples to validate pipeline.
- Caption rendering may depend on local font/ImageMagick availability in some environments.
- If API keys are missing, pipeline falls back with reduced intelligence.
