#!/usr/bin/env python3
"""
Edge TTS для Gospel (English)
Free Microsoft Edge TTS - converts .md to .mp3
"""

import asyncio
import re
import edge_tts
from pathlib import Path

# English voice (female, natural)
VOICE = "en-US-AriaNeural"  # Also: en-US-JennyNeural, en-GB-SoniaNeural

BASE_DIR = Path(__file__).parent


def clean_markdown(text: str) -> str:
    """Removes markdown, keeps clean text for TTS"""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def convert_file(md_path: Path):
    """Converts .md to .mp3"""
    print(f"\n📖 {md_path.name}")

    mp3_path = md_path.with_suffix(".mp3")
    if mp3_path.exists():
        print(f"   ⏭️  Already exists: {mp3_path.name}")
        return

    text = md_path.read_text(encoding="utf-8")
    text = clean_markdown(text)
    print(f"   📝 {len(text)} chars")

    print(f"   🔊 Generating audio...", end=" ", flush=True)

    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(mp3_path))

    size_mb = mp3_path.stat().st_size / (1024 * 1024)
    print(f"✓ ({size_mb:.1f} MB)")


async def main():
    files_to_convert = [
        # Prelude
        BASE_DIR / "00_PRELUDE.md",
        # Tale of the Beginning of Time
        BASE_DIR / "Tale_of_the_Beginning_of_Time" / "Chapter_I_Junos_Day.md",
        BASE_DIR / "Tale_of_the_Beginning_of_Time" / "Chapter_II_Seal_of_Time.md",
        BASE_DIR / "Tale_of_the_Beginning_of_Time" / "Chapter_III_Five_Nodes.md",
        BASE_DIR / "Tale_of_the_Beginning_of_Time" / "Chapter_IV_Comedy.md",
        BASE_DIR / "Tale_of_the_Beginning_of_Time" / "Chapter_V_Order.md",
        # First Act
        BASE_DIR / "First_Act" / "Chapter_I_Simulation.md",
        # Second Act
        BASE_DIR / "Second_Act" / "Chapter_I_Humiliation.md",
        BASE_DIR / "Second_Act" / "Chapter_II_Flow.md",
        BASE_DIR / "Second_Act" / "Chapter_III_Traces.md",
        BASE_DIR / "Second_Act" / "Chapter_IV_Anxieties.md",
    ]

    print("🎙️  Edge TTS (free)")
    print(f"   Voice: {VOICE}")

    for md_file in files_to_convert:
        if md_file.exists():
            await convert_file(md_file)
        else:
            print(f"\n⚠️  Not found: {md_file}")

    print("\n🏁 Done!")


if __name__ == "__main__":
    asyncio.run(main())
