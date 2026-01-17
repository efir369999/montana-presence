#!/usr/bin/env python3
"""
Edge TTS for 福音 (Chinese)
Free Microsoft Edge TTS - converts .md to .mp3

STANDARD VOICE: zh-CN-XiaoxiaoNeural
"""

import asyncio
import re
import edge_tts
from pathlib import Path

# Chinese voice - STANDARD
VOICE = "zh-CN-XiaoxiaoNeural"  # Female, natural

BASE_DIR = Path(__file__).parent


def clean_markdown(text: str) -> str:
    """Removes markdown"""
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
    if mp3_path.exists() and mp3_path.stat().st_size > 0:
        print(f"   ⏭️  Already exists: {mp3_path.name}")
        return

    text = md_path.read_text(encoding="utf-8")
    text = clean_markdown(text)
    print(f"   📝 {len(text)} chars")

    print(f"   🔊 Generating audio...", end=" ", flush=True)

    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(str(mp3_path))
        size_mb = mp3_path.stat().st_size / (1024 * 1024)
        print(f"✓ ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"✗ Error: {e}")


async def main():
    files_to_convert = [
        BASE_DIR / "00. 序曲.md",
        BASE_DIR / "01. 模拟.md",
        BASE_DIR / "02. 屈辱.md",
        BASE_DIR / "03. 心流.md",
        BASE_DIR / "04. 痕迹.md",
        BASE_DIR / "05. 焦虑.md",
        BASE_DIR / "06. 朱诺之日.md",
        BASE_DIR / "07. 时间印章.md",
        BASE_DIR / "08. 五个节点.md",
        BASE_DIR / "09. 喜剧.md",
        BASE_DIR / "10. 秩序.md",
    ]

    print("🎙️  Edge TTS (free)")
    print(f"   Voice: {VOICE} (standard)")

    for md_file in files_to_convert:
        if md_file.exists():
            await convert_file(md_file)
        else:
            print(f"\n⚠️  Not found: {md_file}")

    print("\n🏁 Done!")


if __name__ == "__main__":
    asyncio.run(main())
