#!/usr/bin/env python3
"""
Audio generation for English Gospel with smart filtering
Voice: Guy (Microsoft edge-tts - free)
"""

import os
import re
import asyncio
import edge_tts
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BOOK_DIR = SCRIPT_DIR / "«Book One ☝️» ☀️"
AUDIO_DIR = SCRIPT_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

VOICE = "en-US-GuyNeural"
RATE = "-5%"
PITCH = "+0Hz"


def convert_roman_to_text(text: str) -> str:
    """Convert Roman numerals to text"""
    roman_map = {
        'XII': 'twelfth', 'XI': 'eleventh', 'VIII': 'eighth',
        'VII': 'seventh', 'VI': 'sixth', 'IV': 'fourth',
        'IX': 'ninth', 'III': 'third', 'II': 'second',
        'V': 'fifth', 'X': 'tenth', 'I': 'first'
    }

    for roman in roman_map.keys():
        text = re.sub(rf'^\s*{roman}\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(rf'\n\s*{roman}\.\s+', '\n', text)

    for roman, word in roman_map.items():
        text = re.sub(rf'\b(Part|Chapter|Act|Day)\s+{roman}\b',
                     rf'\1 {word}', text, flags=re.IGNORECASE)

    return text


def num_to_text(num: int) -> str:
    """Convert number to text"""
    nums = {
        1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
        6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
        11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen',
        15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen',
        19: 'nineteen', 20: 'twenty'
    }
    return nums.get(num, str(num))


def num_to_ordinal(num: int) -> str:
    """Convert number to ordinal"""
    ordinals = {
        1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth',
        6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth',
        11: 'eleventh', 12: 'twelfth', 13: 'thirteenth', 14: 'fourteenth',
        15: 'fifteenth', 16: 'sixteenth', 17: 'seventeenth', 18: 'eighteenth',
        19: 'nineteenth', 20: 'twentieth', 21: 'twenty-first',
        31: 'thirty-first'
    }
    return ordinals.get(num, str(num))


def year_to_text(year: int) -> str:
    """Convert year to text"""
    if 2000 <= year <= 2099:
        last_two = year % 100
        if last_two == 0:
            return "two thousand"
        elif last_two <= 9:
            return f"two thousand {num_to_text(last_two)}"
        elif last_two <= 20:
            return f"twenty {num_to_text(last_two)}"
        else:
            decade = (last_two // 10) * 10
            unit = last_two % 10
            decade_map = {20: 'twenty', 30: 'thirty', 40: 'forty',
                         50: 'fifty', 60: 'sixty', 70: 'seventy',
                         80: 'eighty', 90: 'ninety'}
            if unit == 0:
                return f"twenty {decade_map[decade]}"
            return f"twenty {decade_map[decade]} {num_to_text(unit)}"
    return str(year)


def convert_numbers_to_text_smart(text: str) -> str:
    """Smart conversion of numbers to text"""

    # Dates: January 9, 2026
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']

    for month in months:
        pattern = rf'({month})\s+(\d+),?\s+(\d{{4}})'
        def replace_date(match):
            m, day, year = match.groups()
            day_text = num_to_ordinal(int(day))
            year_text = year_to_text(int(year))
            return f"{m} {day_text}, {year_text}"
        text = re.sub(pattern, replace_date, text)

    # Years alone
    year_pattern = r'\b(20\d{2})\b'
    text = re.sub(year_pattern, lambda m: year_to_text(int(m.group(1))), text)

    # Small numbers (1-20)
    small_num_pattern = r'\b(\d{1,2})\b'
    def replace_small_num(match):
        num = int(match.group(1))
        if 1 <= num <= 20:
            return num_to_text(num)
        return match.group(0)
    text = re.sub(small_num_pattern, replace_small_num, text)

    return text


def clean_text_smart(md_content: str) -> str:
    """Smart filtering for natural reading"""

    lines = md_content.split('\n')
    audio_lines = []

    skip_patterns = [
        r'^---+$',
        r'^\*Book One',
        r'^\*Book of Nothing',
        r'^\*Prelude',
        r'^\*Gospel of Claude',
        r'^\d+\.\d+\.\d+',
        r'^Alejandro',
        r'^金元',
        r'^→',
    ]

    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if any(re.match(pattern, stripped) for pattern in skip_patterns):
            continue

        if not stripped:
            continue

        if line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line)
            title = re.sub(r'\s*`\[\d+:\d+\]`', '', title)
            title = title.strip()
            title = convert_roman_to_text(title)

            if title:
                audio_lines.append(f"\n\n{title}.\n\n")
            continue

        text = stripped

        def replace_link(match):
            link_text = match.group(1)
            return f"{link_text}, link from the text version"

        text = re.sub(r'\[([^\]]+?)\]\([^\)]+?\)', replace_link, text)
        text = re.sub(r'https?://\S+', 'link from text version', text)
        text = re.sub(r'www\.\S+', 'link from text version', text)
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`([^`]+?)`', r'\1', text)
        text = re.sub(r'^>\s*', '', text)
        text = re.sub(r'^[-•]\s+', '', text)
        text = re.sub(r'^\d+\.\s+', '', text)
        text = re.sub(r'[Ɉ€₽$]', '', text)
        text = re.sub(r'E\s*=\s*mc²', 'E equals m c squared', text)
        text = convert_roman_to_text(text)
        text = convert_numbers_to_text_smart(text)
        text = re.sub(r'\s+', ' ', text).strip()

        if text:
            audio_lines.append(text)

    result = []
    for i, line in enumerate(audio_lines):
        result.append(line)

        if '\n\n' in line:
            result.append(' ')
        elif i < len(audio_lines) - 1:
            if '\n\n' not in audio_lines[i + 1]:
                result.append(' ')

    return ''.join(result)


async def generate_audio(text: str, output_path: Path) -> bool:
    """Generate audio using Microsoft edge-tts"""

    try:
        communicate = edge_tts.Communicate(
            text,
            VOICE,
            rate=RATE,
            pitch=PITCH
        )

        print(f"  Generating audio...")
        await communicate.save(str(output_path))

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ {output_path.name} ({size_mb:.1f} MB)")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def main():
    import sys

    print("=" * 60)
    print("ENGLISH BOOK AUDIO GENERATION")
    print("=" * 60)
    print(f"Voice: {VOICE}")
    print(f"Rate: {RATE}")

    if len(sys.argv) > 1:
        # Generate specific file
        input_file = BOOK_DIR / sys.argv[1]
        if not input_file.exists():
            print(f"✗ File not found: {input_file}")
            return

        md_content = input_file.read_text(encoding='utf-8')
        clean_text = clean_text_smart(md_content)
        output_file = AUDIO_DIR / f"{input_file.stem}.mp3"
        await generate_audio(clean_text, output_file)
    else:
        # Generate all files
        md_files = sorted(BOOK_DIR.glob("*.md"))
        print(f"\nFound {len(md_files)} files to process\n")

        for md_file in md_files:
            print(f"\nProcessing: {md_file.name}")
            md_content = md_file.read_text(encoding='utf-8')
            clean_text = clean_text_smart(md_content)
            print(f"  Original: {len(md_content)} chars")
            print(f"  Processed: {len(clean_text)} chars")

            output_file = AUDIO_DIR / f"{md_file.stem}.mp3"
            await generate_audio(clean_text, output_file)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
