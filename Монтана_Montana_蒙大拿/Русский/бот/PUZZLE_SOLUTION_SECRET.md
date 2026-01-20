# Ɉ MONTANA PUZZLE — РЕШЕНИЕ (СЕКРЕТНО)

**НЕ ПУБЛИКОВАТЬ!** Это файл для автора.

---

## Структура загадки

```
┌─────────────────────────────────────────────────────────┐
│  ИЗОБРАЖЕНИЕ: cicada_puzzle.png                         │
├─────────────────────────────────────────────────────────┤
│  Слой 1: LSB Steganography                              │
│  ↓                                                       │
│  BEGIN.MONTANA.ZXUKT0LNKEa...END.MONTANA               │
│  ↓                                                       │
│  Слой 2: Caesar Cipher (сдвиг +3)                       │
│  Подсказка: 3301 → первая цифра = 3                     │
│  ↓                                                       │
│  Слой 3: Base64                                         │
│  Подсказка: координаты 64.000000                        │
│  ↓                                                       │
│  Слой 4: XOR с ключом "1033"                            │
│  Подсказка: "3301 : 1033" = зеркало времени             │
│  ↓                                                       │
│  ФИНАЛ: https://github.com/efir369999/-_Nothing_-       │
└─────────────────────────────────────────────────────────┘
```

---

## Подсказки на изображении

| Координата | Подсказка |
|------------|-----------|
| 33.010000, 103.300000 | 3301 и 1033 — ключи |
| 64.000000, 64.000000 | Base64 |
| 88.888888, 88.888888 | LSB = 8 бит |
| 25.121225, 20.260109 | Даты: 25.12.2025, 09.01.2026 |
| "3301 : 1033" | Время и его зеркало |

---

## Код решения

```python
from PIL import Image
import base64

def decode_lsb(img_path):
    """Слой 1: Извлечь LSB"""
    img = Image.open(img_path).convert('RGB')
    pixels = img.load()
    binary = ''
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = pixels[x, y]
            binary += str(r & 1)
    message = ''
    for i in range(0, len(binary), 8):
        byte = binary[i:i+8]
        if len(byte) == 8:
            char_code = int(byte, 2)
            if char_code == 0:
                break
            message += chr(char_code)
    return message

def caesar_shift(text, shift):
    """Слой 2: Caesar cipher"""
    result = []
    for char in text:
        if char.isalpha():
            base = ord('a') if char.islower() else ord('A')
            result.append(chr((ord(char) - base + shift) % 26 + base))
        else:
            result.append(char)
    return ''.join(result)

def xor_decrypt(text, key):
    """Слой 4: XOR"""
    result = []
    for i, char in enumerate(text):
        result.append(chr(ord(char) ^ ord(key[i % len(key)])))
    return ''.join(result)

# РЕШЕНИЕ
raw = decode_lsb('cicada_puzzle.png')
data = raw.split("BEGIN.MONTANA.")[1].split(".END.MONTANA")[0]
step2 = caesar_shift(data, -3)           # Обратный Caesar
step3 = base64.b64decode(step2).decode('latin-1')  # Base64
final = xor_decrypt(step3, "1033")       # XOR с ключом

print(final)  # https://github.com/efir369999/-_Nothing_-
```

---

## Ожидаемое время решения

| Этап | Сложность | Время |
|------|-----------|-------|
| Найти LSB | Средняя | 1-3 дня |
| Понять маркеры | Лёгкая | 1 день |
| Найти Caesar +3 | Средняя | 3-7 дней |
| Понять Base64 | Лёгкая | 1-2 дня |
| Найти ключ XOR | Сложная | 1-2 недели |
| **ИТОГО** | | **2-4 недели** |

---

## Если застрянут

Можно выкладывать подсказки:

1. **Неделя 1**: "Картинка говорит больше, чем показывает"
2. **Неделя 2**: "3301 → 3. Время сдвигает буквы"
3. **Неделя 3**: "64 бита кодируют 6 символов"
4. **Неделя 4**: "Зеркало 3301 — это ключ"

---

*Ɉ Montana — Time is the only real currency*
