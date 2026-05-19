#!/usr/bin/env python3
"""
Конвертация SVG аватарки в PNG для Telegram бота
Требования: pip install cairosvg
"""

import cairosvg
import os

# Пути
script_dir = os.path.dirname(__file__)
svg_path = os.path.join(script_dir, "artef", "bot_avatar.svg")
png_path = os.path.join(script_dir, "artef", "bot_avatar.png")

# Конвертация
print(f"🎨 Конвертация {svg_path} → {png_path}...")

cairosvg.svg2png(
    url=svg_path,
    write_to=png_path,
    output_width=512,
    output_height=512
)

print(f"✅ Готово! Размер: 512x512px")
print(f"📁 Файл: {png_path}")
