#!/usr/bin/env python3
"""Transcribe a video from a URL."""

import argparse
import re
import sys
import tempfile
import textwrap
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "transcriptions"


# Helpers
def safe_name(text: str, maxlen: int = 120) -> str:
    """Make a string safe to use as a filename."""
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", text)
    text = re.sub(r"\s+", " ", text).strip().strip(".")
    return text[:maxlen].rstrip() or "video"


def fmt_ts(seconds: float, srt: bool = False) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}" if srt else f"{h:02d}:{m:02d}:{s:02d}"


def get_info(url: str) -> dict:
    """Fetch video metadata without downloading anything."""
    from yt_dlp import YoutubeDL

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


# Transcript sources
def captions_from_youtube(video_id: str, languages: list[str]) -> list[dict]:
    """Grab existing YouTube captions (manual preferred, auto-generated otherwise)."""
    from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

    transcripts = YouTubeTranscriptApi().list(video_id)
    try:
        transcript = transcripts.find_transcript(languages)
    except NoTranscriptFound:
        transcript = next(iter(transcripts))  # fall back to whatever exists

    segments = []
    for snip in transcript.fetch():
        text = snip.text.replace("\n", " ").strip()
        if text:
            segments.append({"start": snip.start, "end": snip.start + snip.duration, "text": text})
    return segments


def transcribe_with_whisper(url: str, model_size: str, language: str | None) -> list[dict]:
    """Download audio with yt-dlp and transcribe locally with faster-whisper."""
    from faster_whisper import WhisperModel
    from yt_dlp import YoutubeDL

    with tempfile.TemporaryDirectory() as tmp:
        print("  Downloading audio...")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(tmp) / "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        audio = next(Path(tmp).iterdir())

        print(f"  Transcribing with Whisper '{model_size}' (first run downloads the model)...")
        model = WhisperModel(model_size, device="auto", compute_type="auto")
        seg_iter, info = model.transcribe(str(audio), language=language, vad_filter=True)

        segments = []
        for seg in seg_iter:
            text = seg.text.strip()
            if text:
                segments.append({"start": seg.start, "end": seg.end, "text": text})
            if info.duration:
                pct = min(100, int(seg.end / info.duration * 100))
                print(f"\r  Progress: {pct}%", end="", flush=True)
        print()
        return segments


# Output
def render_txt(segments: list[dict], header: str, timestamps: bool) -> str:
    if timestamps:
        body = "\n".join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in segments)
    else:
        joined = " ".join(s["text"] for s in segments)
        body = textwrap.fill(joined, width=100)
    return f"{header}\n\n{body}\n"


def render_srt(segments: list[dict]) -> str:
    blocks = []
    for i, s in enumerate(segments, 1):
        blocks.append(f"{i}\n{fmt_ts(s['start'], True)} --> {fmt_ts(s['end'], True)}\n{s['text']}\n")
    return "\n".join(blocks)


# Main
def process(url: str, args: argparse.Namespace) -> None:
    print(f"\n{url}")
    info = get_info(url)
    title = info.get("title") or "video"
    video_id = info.get("id", "")
    is_youtube = info.get("extractor_key") == "Youtube"
    print(f"  Title: {title}")

    segments: list[dict] = []
    source = ""

    if is_youtube and not args.whisper:
        try:
            languages = [args.language] if args.language else ["en"]
            segments = captions_from_youtube(video_id, languages)
            source = "YouTube captions"
            print(f"  Using existing YouTube captions ({len(segments)} lines).")
        except Exception as e:
            print(f"  No usable captions ({type(e).__name__}); falling back to Whisper.")

    if not segments:
        segments = transcribe_with_whisper(url, args.model, args.language)
        source = f"Whisper ({args.model})"

    if not segments:
        print("  No speech found, nothing saved.")
        return

    OUT_DIR.mkdir(exist_ok=True)
    stem = safe_name(f"{title} [{video_id}]" if video_id else title)

    header = f"{title}\n{url}\nSource: {source}"
    txt_path = OUT_DIR / f"{stem}.txt"
    txt_path.write_text(render_txt(segments, header, args.timestamps), encoding="utf-8")
    print(f"  Saved: {txt_path}")

    if args.srt:
        srt_path = OUT_DIR / f"{stem}.srt"
        srt_path.write_text(render_srt(segments), encoding="utf-8")
        print(f"  Saved: {srt_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Transcribe a video from a URL (YouTube-focused).")
    p.add_argument("urls", nargs="*", help="Video URL(s). If omitted, you'll be prompted.")
    p.add_argument("--whisper", action="store_true",
                   help="Skip YouTube captions and always transcribe the audio with Whisper.")
    p.add_argument("--model", default="base",
                   help="Whisper model: tiny, base, small, medium, large-v3 (default: base).")
    p.add_argument("--language", default=None,
                   help="Language code, e.g. en, pl, de. Whisper auto-detects if omitted; "
                        "captions default to English, then any available language.")
    p.add_argument("--timestamps", action="store_true", help="Put a [HH:MM:SS] timestamp on each line of the .txt.")
    p.add_argument("--srt", action="store_true", help="Also save an .srt subtitle file.")
    args = p.parse_args()

    urls = args.urls or [input("Video URL: ").strip()]
    urls = [u for u in urls if u]
    if not urls:
        sys.exit("No URL given.")

    failed = 0
    for url in urls:
        try:
            process(url, args)
        except Exception as e:
            failed += 1
            print(f"  Failed: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()