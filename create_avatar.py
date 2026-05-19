#!/usr/bin/env python3
"""
Создание PNG аватарки для Telegram бота
Требования: pip install pillow
"""

from PIL import Image, ImageDraw
import math
import os

# Пути
script_dir = os.path.dirname(__file__)
png_path = os.path.join(script_dir, "artef", "bot_avatar.png")

# Размеры
SIZE = 512
CENTER = SIZE // 2

print(f"🎨 Создание аватарки {SIZE}x{SIZE}...")

# Создаём изображение с градиентом
img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Градиентный фон (indigo → purple)
for y in range(SIZE):
    r = int(76 + (168 - 76) * y / SIZE)  # #4c1d95 → #a855f7
    g = int(29 + (85 - 29) * y / SIZE)
    b = int(149 + (247 - 149) * y / SIZE)
    draw.line([(0, y), (SIZE, y)], fill=(r, g, b))

# Внешние кольца
draw.ellipse([56, 56, 456, 456], outline=(255, 255, 255, 76), width=2)
draw.ellipse([76, 76, 436, 436], outline=(255, 255, 255, 51), width=1)

# Центральный элемент - глаз/оракул
# Внешний эллипс
draw.ellipse([176, 196, 336, 316], fill=(255, 255, 255, 25))
# Внутренний эллипс
draw.ellipse([206, 221, 306, 291], fill=(255, 255, 255, 51))
# Центральный круг
draw.ellipse([241, 241, 271, 271], fill=(255, 255, 255, 230))

# Лучи от центра
ray_color = (255, 255, 255, 102)
rays = [
    (CENTER, 100, CENTER, 150),      # верх
    (CENTER, 362, CENTER, 412),      # низ
    (100, CENTER, 150, CENTER),      # лево
    (362, CENTER, 412, CENTER),      # право
    (156, 156, 190, 190),            # верх-лево
    (322, 322, 356, 356),            # низ-право
    (156, 356, 190, 322),            # низ-лево
    (322, 190, 356, 156),            # верх-право
]

for x1, y1, x2, y2 in rays:
    draw.line([(x1, y1), (x2, y2)], fill=ray_color, width=2)

# Звёзды/искры
stars = [
    (180, 120, 3),
    (332, 140, 2),
    (140, 332, 2),
    (372, 300, 3),
    (256, 80, 2),
    (256, 432, 2),
    (80, 256, 2),
    (432, 256, 2),
]

for x, y, r in stars:
    draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, 204))

# Сохраняем
img.save(png_path, 'PNG')
print(f"✅ Готово! Размер: {SIZE}x{SIZE}px")
print(f"📁 Файл: {png_path}")
