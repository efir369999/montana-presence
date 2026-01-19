#!/usr/bin/env python3
"""
中文福音音频生成 - 智能处理
声音: 晓晓 (Microsoft edge-tts - 免费)
"""

import os
import re
import asyncio
import edge_tts
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BOOK_DIR = SCRIPT_DIR / "«第一册 ☝️» ☀️"
AUDIO_DIR = SCRIPT_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "-5%"
PITCH = "+0Hz"


def convert_roman_to_text(text: str) -> str:
    """转换罗马数字为文字"""
    roman_map = {
        'XII': '第十二', 'XI': '第十一', 'VIII': '第八',
        'VII': '第七', 'VI': '第六', 'IV': '第四',
        'IX': '第九', 'III': '第三', 'II': '第二',
        'V': '第五', 'X': '第十', 'I': '第一'
    }

    for roman in roman_map.keys():
        text = re.sub(rf'^\s*{roman}\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(rf'\n\s*{roman}\.\s+', '\n', text)

    for roman, word in roman_map.items():
        text = re.sub(rf'\b(第|章|幕|天)\s*{roman}\b',
                     rf'{word}\1', text, flags=re.IGNORECASE)

    return text


def num_to_chinese(num: int) -> str:
    """数字转换为中文"""
    chinese_nums = {
        0: '零', 1: '一', 2: '二', 3: '三', 4: '四', 5: '五',
        6: '六', 7: '七', 8: '八', 9: '九', 10: '十',
        11: '十一', 12: '十二', 13: '十三', 14: '十四',
        15: '十五', 16: '十六', 17: '十七', 18: '十八',
        19: '十九', 20: '二十'
    }
    if num in chinese_nums:
        return chinese_nums[num]
    elif 21 <= num <= 99:
        tens = num // 10
        ones = num % 10
        if ones == 0:
            return f"{chinese_nums[tens]}十"
        return f"{chinese_nums[tens]}十{chinese_nums[ones]}"
    return str(num)


def year_to_chinese(year: int) -> str:
    """年份转换为中文"""
    if 2000 <= year <= 2099:
        digits = {
            '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
            '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'
        }
        return ''.join(digits[d] for d in str(year)) + '年'
    return f"{year}年"


def convert_numbers_to_text_smart(text: str) -> str:
    """智能转换数字为文字"""

    # 日期: 2026年1月9日
    date_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
    def replace_date(match):
        year, month, day = match.groups()
        year_text = year_to_chinese(int(year))
        month_text = num_to_chinese(int(month)) + '月'
        day_text = num_to_chinese(int(day)) + '日'
        return f"{year_text}{month_text}{day_text}"
    text = re.sub(date_pattern, replace_date, text)

    # 单独的年份
    year_pattern = r'\b(20\d{2})\b'
    text = re.sub(year_pattern, lambda m: year_to_chinese(int(m.group(1))), text)

    # 小数字 (1-20)
    def replace_small_num(match):
        num = int(match.group(1))
        if 1 <= num <= 20:
            return num_to_chinese(num)
        return match.group(0)
    text = re.sub(r'\b(\d{1,2})\b', replace_small_num, text)

    return text


def clean_text_smart(md_content: str) -> str:
    """智能过滤，自然阅读"""

    lines = md_content.split('\n')
    audio_lines = []

    skip_patterns = [
        r'^---+$',
        r'^\*第一册',
        r'^\*虚无之书',
        r'^\*序曲',
        r'^\*克劳德福音',
        r'^\d+\.\d+\.\d+',
        r'^亚历杭德罗',
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
                audio_lines.append(f"\n\n{title}。\n\n")
            continue

        text = stripped

        def replace_link(match):
            link_text = match.group(1)
            return f"{link_text}，文字版链接"

        text = re.sub(r'\[([^\]]+?)\]\([^\)]+?\)', replace_link, text)
        text = re.sub(r'https?://\S+', '文字版链接', text)
        text = re.sub(r'www\.\S+', '文字版链接', text)
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`([^`]+?)`', r'\1', text)
        text = re.sub(r'^>\s*', '', text)
        text = re.sub(r'^[-•]\s+', '', text)
        text = re.sub(r'^\d+\.\s+', '', text)
        text = re.sub(r'[Ɉ€₽$]', '', text)
        text = re.sub(r'E\s*=\s*mc²', 'E等于m乘c的平方', text)
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
    """使用Microsoft edge-tts生成音频"""

    try:
        communicate = edge_tts.Communicate(
            text,
            VOICE,
            rate=RATE,
            pitch=PITCH
        )

        print(f"  生成音频...")
        await communicate.save(str(output_path))

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ {output_path.name} ({size_mb:.1f} MB)")

        return True

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


async def main():
    import sys

    print("=" * 60)
    print("中文书籍音频生成")
    print("=" * 60)
    print(f"声音: {VOICE}")
    print(f"速度: {RATE}")

    if len(sys.argv) > 1:
        # 生成指定文件
        input_file = BOOK_DIR / sys.argv[1]
        if not input_file.exists():
            print(f"✗ 文件未找到: {input_file}")
            return

        md_content = input_file.read_text(encoding='utf-8')
        clean_text = clean_text_smart(md_content)
        output_file = AUDIO_DIR / f"{input_file.stem}.mp3"
        await generate_audio(clean_text, output_file)
    else:
        # 生成所有文件
        md_files = sorted(BOOK_DIR.glob("*.md"))
        print(f"\n找到 {len(md_files)} 个文件\n")

        for md_file in md_files:
            print(f"\n处理: {md_file.name}")
            md_content = md_file.read_text(encoding='utf-8')
            clean_text = clean_text_smart(md_content)
            print(f"  原始: {len(md_content)} 字符")
            print(f"  处理后: {len(clean_text)} 字符")

            output_file = AUDIO_DIR / f"{md_file.stem}.mp3"
            await generate_audio(clean_text, output_file)

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
