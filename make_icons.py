#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成按钮扁平图标（4x 超采样抗锯齿），输出到 icons/ 目录。"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
os.makedirs(OUT, exist_ok=True)

S = 160          # 超采样画布
COLOR = (79, 91, 114, 255)   # 石板蓝灰

def canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))

def save(img, name):
    img = img.resize((32, 32), Image.LANCZOS)
    img.save(os.path.join(OUT, name))

def w_round(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)

def clip(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)

def line(d, pts, w, fill):
    d.line(pts, fill=fill, width=w, joint="curve")

def poly(d, pts, fill):
    d.polygon(pts, fill=fill)

# ---- 粘贴: 剪贴板 ----
im = canvas(); d = ImageDraw.Draw(im)
clip(d, (64, 24, 96, 44), 6, COLOR)          # 顶部夹子
w_round(d, (44, 40, 116, 136), 12, COLOR)    # 板身
d.rectangle((62, 60, 98, 70), fill=(255, 255, 255, 255))   # 三条白线
d.rectangle((62, 82, 98, 92), fill=(255, 255, 255, 255))
d.rectangle((62, 104, 98, 114), fill=(255, 255, 255, 255))
save(im, "paste.png")

# ---- 清空: 垃圾桶 ----
im = canvas(); d = ImageDraw.Draw(im)
d.rounded_rectangle((72, 20, 88, 36), radius=4, fill=COLOR)   # 提手
w_round(d, (36, 36, 124, 52), 8, COLOR)                        # 盖子
poly(d, [(48, 52), (112, 52), (106, 136), (54, 136)], COLOR)   # 桶身
d.rectangle((64, 68, 74, 118), fill=(255, 255, 255, 255))      # 内部竖线
d.rectangle((86, 68, 96, 118), fill=(255, 255, 255, 255))
save(im, "clear.png")

# ---- 解析: 放大镜 ----
im = canvas(); d = ImageDraw.Draw(im)
d.ellipse((32, 32, 112, 112), outline=COLOR, width=16)         # 镜圈
line(d, [(104, 104), (136, 136)], 16, COLOR)                    # 手柄
save(im, "parse.png")

# ---- 开始: 下载箭头 + 托盘 ----
im = canvas(); d = ImageDraw.Draw(im)
d.rectangle((74, 32, 86, 96), fill=COLOR)                       # 竖杆
poly(d, [(56, 84), (104, 84), (80, 116)], COLOR)                # 箭头
d.rounded_rectangle((40, 116, 120, 132), radius=8, fill=COLOR)  # 托盘
save(im, "start.png")

# ---- 停止: 实心方块 ----
im = canvas(); d = ImageDraw.Draw(im)
w_round(d, (48, 48, 112, 112), 14, COLOR)
save(im, "stop.png")

# ---- 打开/浏览: 文件夹 ----
im = canvas(); d = ImageDraw.Draw(im)
w_round(d, (32, 40, 96, 58), 8, COLOR)          # 背板
w_round(d, (32, 58, 128, 124), 10, COLOR)       # 前夹
save(im, "folder.png")

print("生成完成:", sorted(os.listdir(OUT)))
