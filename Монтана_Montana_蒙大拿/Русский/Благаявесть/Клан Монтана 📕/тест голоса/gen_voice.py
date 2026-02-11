#!/usr/bin/env python3
"""Генерация Прелюдии одним голосом. Аргумент: имя голоса."""
import sys, re, subprocess, tempfile, shutil
from pathlib import Path
from openai import OpenAI

voice = sys.argv[1]
speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
src_name = sys.argv[3] if len(sys.argv) > 3 else "00. Прелюдия.md"
src = Path(__file__).parent.parent / src_name
out_dir = Path(__file__).parent

# API key from keychain
key = subprocess.run(
    ['security','find-generic-password','-a','montana','-s','OPENAI_API_KEY','-w'],
    capture_output=True, text=True
).stdout.strip()
client = OpenAI(api_key=key)

# Clean markdown
md = src.read_text()
skip = [r'^---+$', r'^\*«Клан', r'^\*До первого', r'^金元', r'^Найдёмся']
lines = md.split('\n')
parts = []
for l in lines:
    s = l.strip()
    if not s:
        continue
    if any(re.match(p, s) for p in skip):
        continue
    if l.startswith('#'):
        t = re.sub(r'^#+\s*', '', l).strip()
        if t:
            parts.append(t + '.')
        continue
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = t.replace('Ɉ', '').replace('📕', '')
    t = re.sub(r'\s+', ' ', t).strip()
    if t:
        parts.append(t)

# Join with paragraph breaks for natural pauses
text = '\n\n'.join(parts)

# Split into chunks < 4000 chars
sentences = re.split(r'(?<=[.!?…»])\s+', text)
chunks, cur = [], ''
for s in sentences:
    if not s.strip():
        continue
    if len(cur) + len(s) + 1 > 4000:
        if cur:
            chunks.append(cur.strip())
        cur = s
    else:
        cur = f'{cur} {s}' if cur else s
if cur.strip():
    chunks.append(cur.strip())

print(f'[{voice}] {len(text)} chars, {len(chunks)} chunks')

# Generate
tmpdir = Path(tempfile.mkdtemp())
chunk_files = []
for i, ch in enumerate(chunks):
    cf = tmpdir / f'c{i:03d}.mp3'
    r = client.audio.speech.create(model='tts-1-hd', voice=voice, input=ch, response_format='mp3', speed=speed)
    r.stream_to_file(str(cf))
    chunk_files.append(cf)
    print(f'  [{voice}] speed={speed} chunk {i+1}/{len(chunks)} OK')

# Concat
stem = Path(src_name).stem
suffix = f"_{voice}" if speed == 1.0 else f"_{voice}_{speed}"
out_file = out_dir / f'{stem}{suffix}.mp3'
if len(chunk_files) == 1:
    shutil.copy(str(chunk_files[0]), str(out_file))
else:
    lst = tmpdir / 'list.txt'
    lst.write_text('\n'.join(f"file '{f}'" for f in chunk_files))
    subprocess.run(
        ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out_file)],
        capture_output=True
    )

shutil.rmtree(tmpdir, ignore_errors=True)
sz = out_file.stat().st_size / (1024 * 1024)
print(f'[{voice}] DONE: {out_file.name} ({sz:.1f} MB)')
