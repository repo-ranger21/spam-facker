#!/usr/bin/env python3
"""
scripts/generate_fillers.py
============================
One-time (or force-refresh) script to pre-render filler audio for all agents.

Idempotent by default: skips files that already exist unless --force is passed.
Fillers are saved to:  static/tts/fillers/{agent_slug}/{idx:02d}.mp3

Usage:
    python -m scripts.generate_fillers
    python -m scripts.generate_fillers --force
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

# Allow running from the workspace root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import AGENTS  # noqa: E402
from tts import synthesize  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FILLERS_DIR = Path("static/tts/fillers")


def main(force: bool = False) -> None:
    FILLERS_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    failed = 0

    for agent_key, agent in AGENTS.items():
        filler_lines = agent.get("filler_lines")
        voice_id = agent.get("elevenlabs_voice_id")

        if not filler_lines or not voice_id:
            logger.info("Skipping %s: no filler_lines or elevenlabs_voice_id", agent_key)
            continue

        agent_slug = agent["name"].lower()
        agent_dir = FILLERS_DIR / agent_slug
        agent_dir.mkdir(parents=True, exist_ok=True)

        for idx, line in enumerate(filler_lines):
            out_path = agent_dir / f"{idx:02d}.mp3"

            if out_path.exists() and not force:
                logger.info("Skipping  %s/%02d.mp3  (already exists)", agent_slug, idx)
                skipped += 1
                continue

            logger.info("Generating %s/%02d.mp3  %r", agent_slug, idx, line)
            src = synthesize(line, voice_id, call_sid=f"filler_{agent_key}_{idx:02d}")
            if src:
                shutil.copy2(src, out_path)
                logger.info("  Saved -> %s", out_path)
                generated += 1
            else:
                logger.error("  FAILED  %s/%02d.mp3", agent_slug, idx)
                failed += 1

    logger.info(
        "Done.  generated=%d  skipped=%d  failed=%d", generated, skipped, failed
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pre-render filler audio for all SpamFacker agents."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing filler files.",
    )
    args = parser.parse_args()
    main(force=args.force)
