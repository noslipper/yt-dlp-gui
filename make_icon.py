# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（现代扁平风格：圆角渐变 + 下载箭头）"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
SIZE = 256

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

margin = 8
rect = [margin, margin, SIZE - margin, SIZE - margin]
radius = 56
top = "#FF6B6B"
bot = "#C1121F"
steps = 200
for i in range(steps):
    y = rect[1] + (rect[3] - rect[1]) * i / steps
    t = i / (steps - 1)
    r = int(int(top[1:3], 16) + (int(bot[1:3], 16) - int(top[1:3], 16)) * t)
    g = int(int(top[3:5], 16) + (int(bot[3:5], 16) - int(top[3:5], 16)) * t)
    b = int(int(top[5:7], 16) + (int(bot[5:7], 16) - int(top[5:7], 16)) * t)
    d.rounded_rectangle([rect[0], y, rect[2], y + (rect[3] - rect[1]) / steps + 1],
                        radius=radius, fill=(r, g, b, 255))

cx, cy = SIZE / 2, SIZE / 2 - 14
w = 34
head = 66
len_total = 108
y_top = cy - len_total // 2 + 14
y_bot = cy + len_total // 2

d.rounded_rectangle([cx - w / 2, y_top, cx + w / 2, y_bot + 18], radius=w / 2, fill="white")
d.polygon([
    (cx - head / 2, y_bot - 6),
    (cx + head / 2, y_bot - 6),
    (cx, y_bot + 34),
], fill="white")
d.rounded_rectangle([cx - 84, cy + 62, cx + 84, cy + 78], radius=9, fill="white")

img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon saved:", OUT, os.path.getsize(OUT), "bytes")
