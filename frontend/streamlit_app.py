from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="AttentionX", page_icon="AX", layout="wide")


def resolve_api_url() -> str:
	env_url = os.getenv("ATTENTIONX_API_URL")
	if env_url:
		return env_url

	workspace_secrets = Path(".streamlit") / "secrets.toml"
	user_secrets = Path.home() / ".streamlit" / "secrets.toml"
	if not workspace_secrets.exists() and not user_secrets.exists():
		return "http://127.0.0.1:8000"

	try:
		return str(st.secrets["ATTENTIONX_API_URL"])
	except Exception:
		return "http://127.0.0.1:8000"


API_URL = resolve_api_url()

st.markdown(
	"""
	<style>
	@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;700&display=swap');
	:root {
		--ax-bg-1: #f7f3e8;
		--ax-bg-2: #e6f7ef;
		--ax-bg-3: #ffe0b8;
		--ax-text: #102224;
		--ax-muted: #2e4a49;
		--ax-accent: #007a6d;
		--ax-accent-2: #f26a2f;
		--ax-card: rgba(255, 255, 255, 0.78);
		--ax-stroke: rgba(16, 34, 36, 0.12);
	}

	html, body, [class*="css"] {
		font-family: 'Plus Jakarta Sans', sans-serif;
		color: var(--ax-text);
	}

	h1, h2, h3, h4, h5, h6 {
		color: #112d2f !important;
	}

	[data-testid="stWidgetLabel"] p,
	[data-testid="stFileUploaderDropzoneInstructions"] div,
	[data-testid="stFileUploaderFileData"] small,
	[data-testid="stCaptionContainer"] p,
	[data-testid="stMarkdownContainer"] p,
	[data-testid="stMarkdownContainer"] li {
		color: #173436 !important;
	}

	[data-testid="stMarkdownContainer"] h1,
	[data-testid="stMarkdownContainer"] h2,
	[data-testid="stMarkdownContainer"] h3 {
		color: #112d2f !important;
	}

	[data-testid="stWidgetLabel"] p {
		font-weight: 700 !important;
	}

	.stApp {
		background:
			radial-gradient(60rem 36rem at 0% 0%, #dbffe8 0, transparent 50%),
			radial-gradient(46rem 30rem at 100% 0%, #ffe4cc 0, transparent 50%),
			radial-gradient(40rem 24rem at 50% 100%, #e6ecff 0, transparent 48%),
			linear-gradient(140deg, var(--ax-bg-1) 0%, var(--ax-bg-2) 42%, var(--ax-bg-3) 100%);
	}

	.block-container {
		padding-top: 1.2rem;
		padding-bottom: 2rem;
		max-width: 1180px;
	}

	.ax-hero {
		position: relative;
		padding: 1.5rem 1.6rem;
		border-radius: 24px;
		overflow: hidden;
		border: 1px solid var(--ax-stroke);
		background: linear-gradient(122deg, rgba(255, 255, 255, 0.72) 0%, rgba(245, 255, 253, 0.62) 36%, rgba(255, 233, 204, 0.7) 100%);
		backdrop-filter: blur(8px);
		box-shadow: 0 24px 50px -36px rgba(0, 0, 0, 0.35);
		animation: ax-rise 620ms ease both;
	}

	.ax-hero,
	.ax-hero * {
		color: #123336 !important;
	}

	.ax-hero::after {
		content: "";
		position: absolute;
		width: 18rem;
		height: 18rem;
		right: -6rem;
		top: -8rem;
		background: radial-gradient(circle, rgba(0, 122, 109, 0.18) 0, rgba(0, 122, 109, 0.0) 66%);
	}

	.ax-kicker {
		display: inline-block;
		padding: 0.2rem 0.72rem;
		border-radius: 999px;
		background: #ebfff9;
		border: 1px solid #0e3f3a22;
		font-weight: 700;
		font-size: 0.8rem;
		letter-spacing: 0.02em;
		color: #0a5b52 !important;
	}

	.ax-title {
		font-family: 'Sora', sans-serif;
		font-size: clamp(2.0rem, 3vw, 3.1rem);
		font-weight: 800;
		line-height: 1.05;
		margin: 0.62rem 0 0.5rem;
		color: #102d31;
	}

	.ax-subtitle {
		font-size: 1.03rem;
		color: var(--ax-muted);
		max-width: 70ch;
		margin-bottom: 0.92rem;
	}

	.ax-stat-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.56rem;
	}

	.ax-stat {
		padding: 0.58rem 0.7rem;
		border-radius: 14px;
		border: 1px solid #10222418;
		background: rgba(255, 255, 255, 0.72);
	}

	.ax-stat-label {
		font-size: 0.74rem;
		color: #395352;
		text-transform: uppercase;
		font-weight: 700;
		letter-spacing: 0.05em;
	}

	.ax-stat-value {
		font-family: 'Sora', sans-serif;
		font-weight: 700;
		font-size: 1rem;
		margin-top: 0.14rem;
	}

	.ax-card {
		border: 1px solid var(--ax-stroke);
		background: var(--ax-card);
		backdrop-filter: blur(8px);
		border-radius: 20px;
		padding: 1.08rem;
		box-shadow: 0 18px 34px -34px rgba(0, 0, 0, 0.35);
		animation: ax-rise 540ms ease both;
	}

	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div {
		border: 1px solid var(--ax-stroke);
		background: var(--ax-card);
		backdrop-filter: blur(8px);
		border-radius: 20px;
		padding: 1.08rem;
		box-shadow: 0 18px 34px -34px rgba(0, 0, 0, 0.35);
	}

	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div p,
	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div span,
	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div li,
	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div h1,
	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div h2,
	[data-testid="stHorizontalBlock"] > [data-testid="column"] > div h3 {
		color: #112d2f !important;
	}

	.ax-card h3 {
		font-family: 'Sora', sans-serif;
		margin-top: 0.15rem;
		margin-bottom: 0.7rem;
		font-size: 1.25rem;
	}

	.ax-step {
		display: flex;
		gap: 0.78rem;
		padding: 0.64rem;
		border: 1px solid #16363522;
		border-radius: 13px;
		background: #f8fffdfa;
		margin-bottom: 0.56rem;
	}

	.ax-step:last-child {
		margin-bottom: 0;
	}

	.ax-step-num {
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 999px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: linear-gradient(145deg, var(--ax-accent), #2e9d90);
		color: #fff;
		font-size: 0.8rem;
		font-weight: 700;
		flex-shrink: 0;
	}

	.ax-step p {
		margin: 0;
		color: #274847;
		font-size: 0.97rem;
	}

	.ax-result-card {
		border: 1px solid #0f2f3018;
		background: linear-gradient(160deg, #ffffffde, #f8fffdc9 60%, #fff6ebcc 100%);
		border-radius: 18px;
		padding: 0.95rem;
		margin-bottom: 0.7rem;
		color: #112d2f !important;
	}

	.ax-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.34rem;
		padding: 0.22rem 0.58rem;
		border-radius: 999px;
		font-size: 0.78rem;
		margin-right: 0.3rem;
		margin-bottom: 0.35rem;
		border: 1px solid #13373522;
		background: #effff9;
		font-weight: 700;
		color: #0f3234 !important;
	}

	.ax-result-hook {
		font-family: 'Sora', sans-serif;
		font-size: 1.08rem;
		font-weight: 700;
		margin-bottom: 0.52rem;
	}

	.stButton > button {
		background: linear-gradient(120deg, #007a6d, #0d9d90 52%, #f26a2f 100%);
		border: 0;
		color: white;
		font-weight: 700;
		padding: 0.58rem 0.78rem;
		border-radius: 12px;
		box-shadow: 0 16px 22px -18px rgba(0, 0, 0, 0.6);
		transition: transform 180ms ease, box-shadow 180ms ease;
	}

	.stButton > button:hover {
		transform: translateY(-1px);
		box-shadow: 0 22px 26px -20px rgba(0, 0, 0, 0.55);
	}

	[data-testid="stFileUploader"] {
		border-radius: 14px;
		border: 1px dashed #0f3c392f;
		background: #fbfffe;
		padding: 0.2rem;
	}

	@keyframes ax-rise {
		from { opacity: 0; transform: translateY(10px); }
		to { opacity: 1; transform: translateY(0); }
	}

	@media (max-width: 960px) {
		[data-testid="stHorizontalBlock"] > [data-testid="column"] > div {
			padding: 0.9rem;
		}
		.ax-stat-grid {
			grid-template-columns: 1fr;
		}
		.ax-title {
			font-size: 2rem;
		}
	}
	</style>
	""",
	unsafe_allow_html=True,
)

st.markdown(
	"""
	<div class="ax-hero">
	  <span class="ax-kicker">AI-Powered Content Repurposing</span>
	  <h1 class="ax-title">AttentionX</h1>
	  <p class="ax-subtitle">Turn one long mentorship session into a week of high-impact vertical shorts with emotional peak detection, dynamic smart-crop, and scroll-stopping captions.</p>
	  <div class="ax-stat-grid">
	    <div class="ax-stat"><div class="ax-stat-label">Engine</div><div class="ax-stat-value">Whisper + Gemini + CV</div></div>
	    <div class="ax-stat"><div class="ax-stat-label">Output</div><div class="ax-stat-value">Auto 9:16 Viral Clips</div></div>
	    <div class="ax-stat"><div class="ax-stat-label">Use Case</div><div class="ax-stat-value">Mentors, Coaches, Creators</div></div>
	  </div>
	</div>
	""",
	unsafe_allow_html=True,
)

left, right = st.columns([1.1, 1.3], gap="large")

with left:
	st.markdown("### Project Input")
	uploaded = st.file_uploader("Upload long-form video", type=["mp4", "mov", "mkv", "avi", "webm"])
	max_clips = st.slider("Number of short clips", min_value=1, max_value=10, value=5)
	language = st.text_input("Language hint (optional)", value="")
	st.caption(f"Backend endpoint: {API_URL}")
	run_btn = st.button("Generate Attention Clips", type="primary", use_container_width=True)

with right:
	st.markdown("### Core Pipeline")
	st.markdown(
		"""
		<div class="ax-step"><div class="ax-step-num">1</div><p>Whisper transcription with timestamped segments to preserve narrative timing.</p></div>
		<div class="ax-step"><div class="ax-step-num">2</div><p>Emotional peak ranking via audio spikes, sentiment score, and optional Gemini hook refinement.</p></div>
		<div class="ax-step"><div class="ax-step-num">3</div><p>MediaPipe face tracking to drive dynamic smart-crop from horizontal to vertical 9:16.</p></div>
		<div class="ax-step"><div class="ax-step-num">4</div><p>High-contrast timed captions with a strong headline designed to stop the scroll.</p></div>
		""",
		unsafe_allow_html=True,
	)


def render_clip_cards(clips: list[dict[str, Any]]) -> None:
	for clip in clips:
		with st.container():
			st.markdown('<div class="ax-result-card">', unsafe_allow_html=True)
			st.markdown(f"<div class='ax-result-hook'>#{clip['rank']} · {clip['hook']}</div>", unsafe_allow_html=True)
			st.markdown(
				"""
				<span class="ax-pill">Score: {score}</span>
				<span class="ax-pill">Duration: {duration}s</span>
				<span class="ax-pill">Window: {start}s - {end}s</span>
				""".format(
					score=clip["score"],
					duration=clip["duration"],
					start=clip["start"],
					end=clip["end"],
				),
				unsafe_allow_html=True,
			)
			st.write(f"Selection reason: {clip['reason']}")
			clip_path = Path(clip["clip_path"])
			if clip_path.exists():
				st.video(str(clip_path))
			st.caption(f"Clip: {clip['clip_path']}")
			st.caption(f"Captions: {clip['caption_path']}")
			st.markdown("</div>", unsafe_allow_html=True)


if run_btn:
	if uploaded is None:
		st.error("Please upload a video first.")
	else:
		with st.spinner("Processing video. This can take a few minutes for long videos..."):
			files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
			data = {
				"max_clips": str(max_clips),
				"language": language.strip(),
			}

			try:
				response = requests.post(f"{API_URL}/process", files=files, data=data, timeout=1800)
				response.raise_for_status()
				result = response.json()
			except Exception as exc:
				st.error(f"API request failed: {exc}")
				st.stop()

		st.success("Processing complete. Your short-form clips are ready.")
		st.markdown("### Top Moments")
		clips = result.get("clips", [])
		if clips:
			render_clip_cards(clips)
		else:
			st.warning("No clips were generated. Try a longer or more speech-dense video.")

		st.markdown("### Debug JSON")
		st.code(json.dumps(result, indent=2), language="json")
