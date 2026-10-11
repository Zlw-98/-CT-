# -*- coding: utf-8 -*-
"""HU阈值 + 几何轮廓法 体成分评估
皮下脂肪SAT = 脂肪像素中，位于"身体外轮廓向内凹陷"之外的部分
更稳健做法：用脂肪像素的形态学判定 —— 对脂肪掩膜做闭运算取外轮廓，外轮廓向内收 N mm 为分界
"""
import os, glob, csv
import numpy as np
import pydicom
from scipy import ndimage

d = r"D:\学习工作\wz\CT影像处理\20261009\ct"
outdir = r"D:\学习工作\wz\CT影像处理\20261009\results"
os.makedirs(outdir, exist_ok=True)
files = sorted(glob.glob(os.path.join(d, "*.dcm")))

FAT = (-190, -30)
MUSCLE = (-29, 150)

rows = []
for f in files:
    ds = pydicom.dcmread(f)
    hu = ds.pixel_array.astype(np.float32) * float(getattr(ds, 'RescaleSlope', 1) or 1) \
         + float(getattr(ds, 'RescaleIntercept', 0) or 0)
    ps = getattr(ds, 'PixelSpacing', None)
    if ps is None:
        continue
    px_mm = float(ps[0])
    px_area = px_mm * px_mm

    # 身体掩膜：非空气
    body = hu > -350
    body = ndimage.binary_fill_holes(body)
    body = ndimage.binary_opening(body, iterations=2)
    body = ndimage.binary_erosion(body, iterations=3)

    fat = body & (hu >= FAT[0]) & (hu <= FAT[1])
    muscle = body & (hu >= MUSCLE[0]) & (hu <= MUSCLE[1])

    # 皮下脂肪判定：脂肪掩膜先做闭运算（填平内部空隙），只保留"外环"
    fat_closed = ndimage.binary_closing(fat, iterations=2)
    # 从图像边界向外做泛洪，越过的区域是体外
    inv = ~body
    lab, n = ndimage.label(inv)
    outside_labels = set()
    for edge in [(0, 0), (0, -1), (-1, 0), (-1, -1)]:
        v = lab[edge]
        if v > 0:
            outside_labels.add(v)
    outside = np.isin(lab, list(outside_labels))
    inside = ~outside

    # 距离变换：每个体内像素到体外的距离
    dist = ndimage.distance_transform_edt(inside)
    # 皮下带：距离体外 < 阈值 的体内区域（约 15mm 内收，贴合皮下脂肪层）
    subcut_band = inside & (dist < 15.0)   # 15 mm
    sat = fat & subcut_band
    vat = fat & ~subcut_band

    rows.append(dict(
        文件=os.path.basename(f),
        患者ID=str(getattr(ds, 'PatientID', '')),
        参数=str(getattr(ds, 'ProtocolName', ''))[:28],
        身体面积cm2=round(body.sum() * px_area / 100, 2),
        总脂肪cm2=round(fat.sum() * px_area / 100, 2),
        皮下脂肪SAT_cm2=round(sat.sum() * px_area / 100, 2),
        内脏脂肪VAT_cm2=round(vat.sum() * px_area / 100, 2),
        骨骼肌SMA_cm2=round(muscle.sum() * px_area / 100, 2),
        肌肉平均HU=round(float(hu[muscle].mean()), 1) if muscle.sum() > 0 else '',
        VAT_SAT比=round(vat.sum() / sat.sum(), 2) if sat.sum() > 0 else '',
    ))

newcols = list(rows[0].keys())
old_path = os.path.join(outdir, "threshold_baseline.csv")
new_path = os.path.join(outdir, "threshold_areas.csv")
with open(new_path, 'w', newline='', encoding='utf-8-sig') as fp:
    w = csv.DictWriter(fp, fieldnames=newcols); w.writeheader(); w.writerows(rows)

import statistics as st
print("处理切片数:", len(rows))
print()
for k in ['身体面积cm2', '总脂肪cm2', '皮下脂肪SAT_cm2', '内脏脂肪VAT_cm2', '骨骼肌SMA_cm2']:
    v = [r[k] for r in rows]
    print(f"{k:16s} 均值{st.mean(v):7.1f}  中位{st.median(v):7.1f}  范围[{min(v):.1f}, {max(v):.1f}]")
print()
print("前6例:")
for r in rows[:6]:
    print(f"  {r['文件']:18s} 皮下SAT={r['皮下脂肪SAT_cm2']:7.1f}  内脏VAT={r['内脏脂肪VAT_cm2']:7.1f}  肌肉={r['骨骼肌SMA_cm2']:7.1f}")
print()
print("CSV:", new_path)
