#!/usr/bin/env python3
"""Generate Montana .icns from СИМВОЛ_ВРЕМЕНИ.PNG — exact colors, 3D volume, rounded corners."""

from PIL import Image, ImageDraw, ImageFilter
import subprocess, os, shutil

SIZE = 1024
CORNER = 228  # macOS squircle ~22%


def rounded_rect_mask(size, radius):
    scale = 4
    big = Image.new('L', (size[0]*scale, size[1]*scale), 0)
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([(0, 0), (size[0]*scale-1, size[1]*scale-1)], radius=radius*scale, fill=255)
    return big.resize(size, Image.LANCZOS)


def extract_symbol(src):
    """Extract only the gold symbol as RGBA with transparent background."""
    w, h = src.size
    px = src.load()

    # Find bbox of non-black pixels
    threshold = 25
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            if r > threshold or g > threshold or b > threshold:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    print(f"Symbol bbox: ({min_x}, {min_y}, {max_x+1}, {max_y+1})")

    # Extract just the symbol with transparency
    sw = max_x - min_x + 1
    sh = max_y - min_y + 1
    symbol = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    spx = symbol.load()

    for y in range(sh):
        for x in range(sw):
            r, g, b = px[min_x + x, min_y + y][:3]
            brightness = max(r, g, b)
            if brightness > threshold:
                spx[x, y] = (r, g, b, 255)
            else:
                spx[x, y] = (0, 0, 0, 0)

    return symbol


def create_icon(source_path):
    src = Image.open(source_path).convert('RGBA')
    symbol = extract_symbol(src)
    cw, ch = symbol.size
    print(f"Symbol size: {cw}x{ch}")

    # Scale symbol to ~55% of icon
    target = int(SIZE * 0.55)
    scale = target / max(cw, ch)
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    symbol = symbol.resize((new_w, new_h), Image.LANCZOS)

    # === BACKGROUND: pure black with subtle depth gradient ===
    canvas = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 255))

    # Subtle radial gradient from center (very subtle warmth)
    for y in range(SIZE):
        for x in range(SIZE):
            dx = (x - SIZE * 0.45) / SIZE
            dy = (y - SIZE * 0.4) / SIZE
            dist = (dx*dx + dy*dy) ** 0.5
            v = max(0, int(10 * (1 - dist * 1.5)))
            canvas.putpixel((x, y), (v, v, v + 1, 255))

    # === SYMBOL PLACEMENT ===
    sx = (SIZE - new_w) // 2
    sy = (SIZE - new_h) // 2

    # Drop shadow
    shadow = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    shadow.paste(symbol, (sx + 6, sy + 8), symbol)
    # Darken shadow
    shpx = shadow.load()
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = shpx[x, y]
            if a > 0:
                shpx[x, y] = (0, 0, 0, min(a, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas, shadow)

    # Main symbol
    canvas.paste(symbol, (sx, sy), symbol)

    # Top highlight (lighter gold on upper part of symbol for 3D)
    hl = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    hl.paste(symbol, (sx, sy), symbol)
    hlpx = hl.load()
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = hlpx[x, y]
            if a > 0:
                local_y = y - sy
                progress = local_y / new_h if new_h > 0 else 1
                if progress < 0.45:
                    alpha = int(40 * (1 - progress / 0.45))
                    hlpx[x, y] = (255, 245, 220, alpha)
                else:
                    hlpx[x, y] = (0, 0, 0, 0)
            else:
                hlpx[x, y] = (0, 0, 0, 0)
    canvas = Image.alpha_composite(canvas, hl)

    # === INNER BEVEL (3D container like Developer icon) ===
    bevel = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bevel)
    # Top-left light edge
    bd.rounded_rectangle([(2, 2), (SIZE-3, SIZE-3)], radius=CORNER-2,
                         outline=(255, 255, 255, 15), width=1)
    canvas = Image.alpha_composite(canvas, bevel)

    # Bottom-right shadow edge
    bevel2 = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    bd2 = ImageDraw.Draw(bevel2)
    bd2.rounded_rectangle([(4, 4), (SIZE-1, SIZE-1)], radius=CORNER-2,
                          outline=(0, 0, 0, 30), width=1)
    canvas = Image.alpha_composite(canvas, bevel2)

    # === ROUNDED CORNERS ===
    mask = rounded_rect_mask((SIZE, SIZE), CORNER)
    final = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    final.paste(canvas, (0, 0), mask)

    return final


def make_icns(img, output_dir):
    iconset = os.path.join(output_dir, 'Montana.iconset')
    if os.path.exists(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        resized = img.resize((s, s), Image.LANCZOS)
        resized.save(os.path.join(iconset, f'icon_{s}x{s}.png'))
        if s <= 512:
            resized2x = img.resize((s * 2, s * 2), Image.LANCZOS)
            resized2x.save(os.path.join(iconset, f'icon_{s}x{s}@2x.png'))

    icns_path = os.path.join(output_dir, 'Montana.icns')
    subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', icns_path], check=True)
    shutil.rmtree(iconset)
    print(f'Created: {icns_path}')


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(script_dir, '..', '..', 'Русский', 'Генезис', 'СИМВОЛ_ВРЕМЕНИ.PNG')
    source = os.path.normpath(source)

    print(f'Source: {source}')
    icon = create_icon(source)

    png_path = os.path.join(script_dir, 'Montana_icon_1024.png')
    icon.save(png_path)
    print(f'Preview: {png_path}')

    make_icns(icon, script_dir)
    print('Done!')
