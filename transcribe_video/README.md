# How it works

For YouTube links, it first tries the video's existing captions. That is instant and needs no download. It prefers manual captions over auto-generated ones.
If there are no captions, or the link isn't YouTube, it downloads the audio with yt-dlp and transcribes it locally with faster-whisper. This doesn't need ffmpeg or an API key.
It saves the result to transcriptions/ next to the script, named ``<title> [<video id>].txt``

# Setup

- pip install yt-dlp youtube-transcript-api faster-whisper

# Example Usage

- python transcribe_video.py "https://www.youtube.com/watch?v=VIDEO_ID"
- python transcribe_video.py URL1 URL2 --timestamps --srt
- python transcribe_video.py URL --whisper --model small --language pl

# Options

With no URL, the script prompts you to paste one.\
--whisper skips the captions and always transcribes the audio.\
--model picks the Whisper size (tiny, base, small, medium, large-v3). The default is base; larger models are more accurate but slower.\
--language sets the language code. Whisper auto-detects it if you leave this out, and captions default to English, then any available language.\
--timestamps adds [HH:MM:SS] to each line.\
--srt also saves a subtitle file.\

If a YouTube link keeps failing on captions, --whisper is a reliable workaround.