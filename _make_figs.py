# -*- coding: utf-8 -*-
"""生成示例分割图 + 分布图，验证阈值法效果"""
import os, glob
import numpy as np
import pydicom
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name()]
        break
plt.rcParams['axes.unicode_minus'] = False

d = r"D:\学习工作\wz\CT影像处理\20261009\ct"
outdir = r"D:\学习工作\wz\CT影像处理\20261009\results"
os.makedirs(outdir, exist_ok=True)
files = sorted(glob.glob(os.path.join(d, "*.dcm")))

FAT = (-190, -30)
MUSCLE = (-29, 150)

def segment(f):
    ds = pydicom.dcmread(f)
    hu = ds.pixel_array.astype(np.float32) * float(getattr(ds, 'RescaleSlope', 1) or 1) \
         + float(getattr(ds, 'RescaleIntercept', 0) or 0)
    ps = getattr(ds, 'PixelSpacing', None)
    px_mm = float(ps[0]); px_area = px_mm * px_mm
    body = ndimage.binary_fill_holes(hu > -350)
    body = ndimage.binary_opening(body, iterations=2)
    body = ndimage.binary_erosion(body, iterations=3)
    fat = body & (hu >= FAT[0]) & (hu <= FAT[1])
    muscle = body & (hu >= MUSCLE[0]) & (hu <= MUSCLE[1])
    inv = ~body
    lab, n = ndimage.label(inv)
    outs = set()
    for e in [(0, 0), (0, -1), (-1, 0), (-1, -1)]:
        if lab[e] > 0: outs.add(lab[e])
    inside = ~np.isin(lab, list(outs))
    dist = ndimage.distance_transform_edt(inside)
    band = inside & (dist < 15.0)
    return hu, body, fat & band, fat & ~band, muscle, px_area, ds

# 选 4 例展示
pick = [files[0], files[3], files[10], files[30]]
fig, axes = plt.subplots(2, 4, figsize=(16, 9))
for i, f in enumerate(pick):
    hu, body, sat, vat, mus, pxa, ds = segment(f)
    ax = axes[0][i]
    ax.imshow(np.clip(hu, -200, 300), cmap='gray')
    ax.set_title(f"{os.path.basename(f)}\n{str(getattr(ds,'ProtocolName',''))[:22]}", fontsize=9)
    ax.axis('off')
    ax = axes[1][i]
    rgb = np.zeros(hu.shape + (3,), dtype=np.uint8)
    rgb[body] = [70, 70, 70]
    rgb[sat] = [255, 215, 0]     # 皮下脂肪 黄
    rgb[vat] = [255, 60, 60]     # 内脏脂肪 红
    rgb[mus] = [60, 160, 255]    # 骨骼肌 蓝
    ax.imshow(rgb)
    t = f"SAT={sat.sum()*pxa/100:.0f}  VAT={vat.sum()*pxa/100:.0f}  SMC={mus.sum()*pxa/100:.0f} cm²"
    ax.set_title(t, fontsize=9)
    ax.axis('off')
axes[0][0].set_ylabel('原始CT', fontsize=11)
axes[1][0].set_ylabel('分割结果', fontsize=11)
plt.suptitle('HU阈值法体成分分割（上：原始CT  下：黄=皮下脂肪 红=内脏脂肪 蓝=骨骼肌）', fontsize=13)
plt.tight_layout()
p1 = os.path.join(outdir, "sample_segmentation.png")
plt.savefig(p1, dpi=110, bbox_inches='tight'); plt.close()
print("图1:", p1)

# 分布图
import csv as _csv
rows = list(_csv.DictReader(open(os.path.join(outdir, "threshold_areas.csv"), encoding='utf-8-sig')))
def col(k): return [float(r[k]) for r in rows]
fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
for ax, (k, c) in zip(axes, [('皮下脂肪SAT_cm2', '#f0a500'), ('内脏脂肪VAT_cm2', '#e04040'), ('骨骼肌SMA_cm2', '#3a86ff')]):
    v = col(k)
    ax.hist(v, bins=16, color=c, alpha=0.85, edgecolor='white')
    ax.axvline(np.mean(v), color='black', ls='--', lw=1.5, label=f'均值 {np.mean(v):.0f}')
    ax.set_title(k, fontsize=11); ax.set_xlabel('cm²'); ax.set_ylabel('例数'); ax.legend(fontsize=9)
plt.suptitle('69例腹部CT切片体成分面积分布（HU阈值法）', fontsize=13)
plt.tight_layout()
p2 = os.path.join(outdir, "distribution.png")
plt.savefig(p2, dpi=110, bbox_inches='tight'); plt.close()
print("图2:", p2)
