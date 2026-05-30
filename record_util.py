"""record_util.py — Download Twilio recording + ffmpeg 9:16 MP4 overlay."""

import logging
import subprocess
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path(__file__).parent / "static" / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def make_mp4(
    recording_url: str,
    call_sid: str,
    account_sid: str,
    auth_token: str,
) -> tuple[str, str]:
    """Download Twilio MP3 and render a 9:16 vertical MP4 with centered text overlay.

    Args:
        recording_url: Twilio RecordingUrl (no extension — .mp3 is appended).
        call_sid: Used as the output filename stem.
        account_sid / auth_token: Twilio credentials for authenticated download.

    Returns:
        (mp3_path, mp4_path) as absolute path strings.

    Raises:
        requests.HTTPError: if the Twilio download fails.
        subprocess.CalledProcessError: if ffmpeg exits non-zero.
    """
    mp3_path = RECORDINGS_DIR / f"{call_sid}.mp3"
    mp4_path = RECORDINGS_DIR / f"{call_sid}.mp4"

    # Twilio requires HTTP Basic auth to download recordings
    resp = requests.get(
        f"{recording_url}.mp3",
        auth=(account_sid, auth_token),
        timeout=120,
        stream=True,
    )
    resp.raise_for_status()
    with mp3_path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
    logger.info("Recording downloaded to %s", mp3_path)

    # lavfi color source = infinite black frames; -shortest stops at audio end
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=360x640:r=24",
        "-i", str(mp3_path),
        "-vf", (
            "drawtext=text='SpamFacker Ops':"
            "fontcolor=white:fontsize=28:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "38",
        "-c:a", "aac", "-b:a", "64k",
        "-shortest",
        str(mp4_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    logger.info("MP4 rendered at %s", mp4_path)

    return str(mp3_path), str(mp4_path)
