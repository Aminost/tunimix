"""YouTube recipe videos: use the transcript (+ title/description) as source text."""
from __future__ import annotations

import re

from . import RawSource
from .web import fetch_html, readable_text


def _video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    if not m:
        raise ValueError(f"Cannot find a YouTube video id in {url}")
    return m.group(1)


def extract_youtube(url: str) -> RawSource:
    vid = _video_id(url)
    transcript = ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        fetched = api.fetch(vid, languages=["ar", "fr", "de", "en"])
        transcript = " ".join(snippet.text for snippet in fetched)
    except Exception as exc:  # no transcript, blocked, etc.
        transcript = f"(no transcript available: {exc.__class__.__name__})"
    title, page_text = "", ""
    try:
        title, page_text = readable_text(fetch_html(url), limit=6000)
    except Exception:
        pass
    text = f"VIDEO TRANSCRIPT:\n{transcript}\n\nPAGE TEXT / DESCRIPTION:\n{page_text}"
    return RawSource(kind="youtube", url=url, title=title, text=text)
