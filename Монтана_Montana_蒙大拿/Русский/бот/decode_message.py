#!/usr/bin/env python3
"""
Ɉ MONTANA — Message Decoder
Extract hidden messages from images using LSB steganography.

Usage: python decode_message.py <image_path>
"""

import sys
from PIL import Image

def decode_message(image_path: str) -> str:
    """Extract hidden message from image using LSB."""
    img = Image.open(image_path).convert('RGB')
    pixels = img.load()

    binary = ''
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = pixels[x, y]
            binary += str(r & 1)

    # Convert binary to text
    message = ''
    for i in range(0, len(binary), 8):
        byte = binary[i:i+8]
        if len(byte) == 8:
            char_code = int(byte, 2)
            if char_code == 0:  # Null terminator
                break
            message += chr(char_code)

    return message

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python decode_message.py <image_path>")
        print("\nɈ Montana — Find the hidden path.")
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        message = decode_message(image_path)
        print(f"\n{'═' * 50}")
        print("Ɉ MONTANA — HIDDEN MESSAGE FOUND")
        print('═' * 50)
        print(f"\n{message}\n")
        print('═' * 50)
        print("Time is the only real currency.")
        print('═' * 50)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
