# -*- coding: utf-8 -*-
"""v3: 几何约束法
骨骼肌 = 腹壁肌肉环(紧贴皮下脂肪内侧的薄层) ∪ 脊柱周围软组织(腰大肌/竖脊肌/椎旁)
内脏脂肪 = 腹壁环围成的"腹腔"内、且非皮下的脂肪
皮下脂肪 = 紧贴体表 15mm 内的脂肪
"""
import os, glob, csv
import numpy as np
import pydicom
from scipy import ndimage

d = r"D:\学习工作\wz\CT影像处理\20261009\ct"
outdir = r"D:\学习工作\wz\CT影像处理\20261009\results"
FAT = (-190, -30)      # 脂肪窗
MUSCLE = (-29, 150)    # 软组织窗
SAT_MM = 22.0          # 皮下脂肪测地厚度上限
WALL_MM = 12.0         # 腹壁肌肉环厚度(皮下脂肪内侧向内)
SPINE_MM = 24.0        # 脊柱两侧肌肉的圆盘半径上限


def analyze(path):
    ds = pydicom.dcmread(path)
    hu = ds.pixel_array.astype(np.float32) * float(getattr(ds, 'RescaleSlope', 1) or 1) \
         + float(getattr(ds, 'RescaleIntercept', 0) or 0)
    ps = getattr(ds, 'PixelSpacing', None)
    if ps is None:
        return None
    px = float(ps[0])
    pxa = px * px

    body = ndimage.binary_fill_holes(hu > -350)
    body = ndimage.binary_opening(body, iterations=2)
    body = ndimage.binary_erosion(body, iterations=3)
    if body.sum() == 0:
        return None, None

    fat = body & (hu >= FAT[0]) & (hu <= FAT[1])
    soft = body & (hu >= MUSCLE[0]) & (hu <= MUSCLE[1])

    # 离体表距离
    lab, n = ndimage.label(~body)
    outs = set(lab[e] for e in [(0, 0), (0, -1), (-1, 0), (-1, -1)] if lab[e] > 0)
    inside = ~np.isin(lab, list(outs))
    dist_surf = ndimage.distance_transform_edt(inside) * px
    can = inside & (hu > -350)   # 体部内解剖区

    # 皮下脂肪 = 沿脂肪路径与体表相连、且测地距离<22mm 的脂肪（测地膨胀，抗断裂）
    sat = fat & (dist_surf < 5.0)
    for _ in range(int(round(SAT_MM / px))):
        sat = fat & ndimage.binary_dilation(sat)
    # 内脏脂肪 = 其余脂肪（与体表不相连/超测地距离）
    vat = fat & ~sat

    # 腹壁肌肉环：紧贴皮下脂肪内侧 12mm 的软组织（排除皮肤）
    d_sat = ndimage.distance_transform_edt(~sat) * px if sat.any() else np.full_like(hu, 1e9)
    wall = can & soft & (d_sat <= WALL_MM) & (dist_surf > 6.0)

    # 脊柱两侧肌肉：从椎体沿软组织洪水填充(脂肪塑形)，生长中排除正前扇形，圆盘半径封顶
    posterior = np.zeros_like(body)
    canal = np.zeros_like(body)
    bone = body & (hu > 200)
    if bone.sum() > 20:
        bl, bc = ndimage.label(bone)
        sizes = ndimage.sum(np.ones_like(bl), bl, index=range(1, bc + 1))
        if len(sizes) > 0:
            spine = (bl == (1 + int(np.argmax(sizes))))
            d_spine = ndimage.distance_transform_edt(~spine) * px
            ys, xs = np.where(spine)
            cy, cx = ys.mean(), xs.mean()
            Y, X = np.mgrid[0:hu.shape[0], 0:hu.shape[1]]
            dy, dx = (Y - cy).astype(float), (X - cx).astype(float)
            norm = np.sqrt(dx * dx + dy * dy) + 1e-6
            anterior = (-dy) / norm                              # 1=正前方(图像上方)
            front = anterior >= np.cos(np.deg2rad(50.0))         # 正前±50°：主动脉/肠管
            posterior = can & soft & (d_spine <= 10.0) & (~front)
            for _ in range(int(round(40.0 / px))):
                posterior = can & soft & (~front) & ndimage.binary_dilation(posterior)
            posterior = posterior & (d_spine <= SPINE_MM)        # 圆盘半径上限
            canal = ndimage.binary_fill_holes(bone) & ~bone      # 椎管(脊髓)+椎体骨髓腔

    muscle = (wall | posterior) & body & (~canal)

    pxa_cm2 = pxa / 100.0
    return hu, dict(
        身体面积cm2=round(body.sum() * pxa_cm2, 2),
        总脂肪cm2=round(fat.sum() * pxa_cm2, 2),
        皮下脂肪SAT_cm2=round(sat.sum() * pxa_cm2, 2),
        内脏脂肪VAT_cm2=round(vat.sum() * pxa_cm2, 2),
        骨骼肌SMA_cm2=round(muscle.sum() * pxa_cm2, 2),
        肌肉平均HU=round(float(hu[muscle].mean()), 1) if muscle.sum() > 0 else '',
        VAT_SAT比=round(vat.sum() / sat.sum(), 2) if sat.sum() > 0 else '',
    ), (body, sat, vat, muscle, px)


files = sorted(glob.glob(os.path.join(d, "*.dcm")))
rows = []
mems = {}
for f in files:
    ds = pydicom.dcmread(f, stop_before_pixels=True)
    res = analyze(f)
    if res is None or res[0] is None:
        continue
    hu, m, mem = res
    mems[os.path.basename(f)] = (hu, mem, str(getattr(ds, 'ProtocolName', '')))
    m2 = dict(文件=os.path.basename(f), 患者ID=str(getattr(ds, 'PatientID', '')),
              参数=str(getattr(ds, 'ProtocolName', ''))[:28], **m)
    rows.append(m2)

with open(os.path.join(outdir, "threshold_areas_v3.csv"), 'w', newline='', encoding='utf-8-sig') as fp:
    w = csv.DictWriter(fp, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

import statistics as st
print("切片数:", len(rows))
for k in ['身体面积cm2', '总脂肪cm2', '皮下脂肪SAT_cm2', '内脏脂肪VAT_cm2', '骨骼肌SMA_cm2']:
    v = [r[k] for r in rows]
    print(f"{k:16s} 均值{st.mean(v):7.1f} 中位{st.median(v):7.1f} 范围[{min(v):.1f}, {max(v):.1f}]")

# 图
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name()]
        break
plt.rcParams['axes.unicode_minus'] = False

pick = [files[0], files[10], files[31], files[45]]
fig, axes = plt.subplots(2, 4, figsize=(16, 9))
for i, f in enumerate(pick):
    bn = os.path.basename(f)
    hu, (body, sat, vat, muscle, px), proto = mems[bn]
    ax = axes[0][i]
    ax.imshow(np.clip(hu, -200, 300), cmap='gray')
    ax.set_title(f"{bn}\n{proto[:22]}", fontsize=9); ax.axis('off')
    ax = axes[1][i]
    rgb = np.zeros(hu.shape + (3,), dtype=np.uint8)
    rgb[body] = [70, 70, 70]; rgb[sat] = [255, 215, 0]
    rgb[vat] = [255, 60, 60]; rgb[muscle] = [60, 160, 255]
    ax.imshow(rgb); ax.axis('off')
    a = px * px / 100
    ax.set_title(f"SAT={sat.sum()*a:.0f} VAT={vat.sum()*a:.0f} SMA={muscle.sum()*a:.0f} cm²", fontsize=9)
axes[0][0].set_ylabel('原始CT', fontsize=11); axes[1][0].set_ylabel('v3分割', fontsize=11)
plt.suptitle('v3 几何约束法（黄=皮下脂肪 红=内脏脂肪 蓝=骨骼肌）', fontsize=13)
plt.tight_layout()
p = os.path.join(outdir, "sample_segmentation_v3.png")
plt.savefig(p, dpi=110, bbox_inches='tight'); plt.close()
print("图:", p)

# 分布图
fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
for ax, (k, c) in zip(axes, [('皮下脂肪SAT_cm2', '#f0a500'), ('内脏脂肪VAT_cm2', '#e04040'), ('骨骼肌SMA_cm2', '#3a86ff')]):
    v = [r[k] for r in rows]
    ax.hist(v, bins=16, color=c, alpha=0.85, edgecolor='white')
    ax.axvline(st.mean(v), color='black', ls='--', lw=1.5, label=f'均值 {st.mean(v):.0f}')
    ax.set_title(k, fontsize=11); ax.set_xlabel('cm²'); ax.set_ylabel('例数'); ax.legend(fontsize=9)
plt.suptitle('69例腹部CT切片体成分面积分布（v3几何约束法）', fontsize=13)
plt.tight_layout()
p2 = os.path.join(outdir, "distribution_v3.png")
plt.savefig(p2, dpi=110, bbox_inches='tight'); plt.close()
print("图:", p2)
print("CSV:", os.path.join(outdir, "threshold_areas_v3.csv"))
