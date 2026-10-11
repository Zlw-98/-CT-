# -*- coding: utf-8 -*-
"""构建脚本：把 ct/ 里若干真实切片「烘焙」成内置示例资产 assets/sample.npz。

仅构建时运行一次。原型运行时只加载该 npz 静态资产，不读 DICOM、不跑 v3 算法。
产出每例：hu(float32)、label(uint8, 0/1/2/3)、body(bool)、px_mm(float)、匿名元数据(JSON)。

用法：
    "C:/Users/Levin Zhang/.workbuddy/binaries/python/envs/default/Scripts/python.exe" _make_sample.py
"""
import os
import sys
import glob
import json
import numpy as np
import pydicom
from scipy import ndimage

try:  # Windows 控制台默认 GBK，避免打印 ² 等字符报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
CT_DIR = os.path.join(ROOT, "ct")
ASSETS_DIR = os.path.join(ROOT, "assets")
OUT_NPZ = os.path.join(ASSETS_DIR, "sample.npz")

# ---- v3 参数（与 _threshold_v3.py 一致，见需求说明书附录A）----
FAT = (-190, -30)      # 脂肪 HU 窗
MUSCLE = (-29, 150)    # 肌肉 HU 窗
SAT_MM = 22.0          # 皮下脂肪测地厚度上限
WALL_MM = 12.0         # 腹壁肌肉环厚度
SPINE_MM = 24.0        # 脊柱两侧肌肉圆盘半径上限

# 挑选的切片下标（在排序后的文件列表中），尽量覆盖不同厂商/层面
PICK_INDICES = [0, 11, 22, 33, 44, 55, 66]

# 匿名化演示元数据（每人一行，按顺序套用）
DEMO_META = [
    ("示例病例01", "男", "056Y"),
    ("示例病例02", "女", "043Y"),
    ("示例病例03", "男", "061Y"),
    ("示例病例04", "女", "035Y"),
    ("示例病例05", "男", "048Y"),
    ("示例病例06", "女", "070Y"),
    ("示例病例07", "男", "052Y"),
]


def read_hu(path):
    """读单层 DICOM -> (hu float32, px_mm, ds)。"""
    ds = pydicom.dcmread(path)
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    hu = ds.pixel_array.astype(np.float32) * slope + intercept
    ps = getattr(ds, "PixelSpacing", None)
    px = float(ps[0]) if ps else 0.75
    return hu, px, ds


def segment_v3(hu, px):
    """v3 几何约束法：返回 (label uint8, body bool)。label: 0背景 1SAT 2VAT 3SMA。"""
    body = ndimage.binary_fill_holes(hu > -350)
    body = ndimage.binary_opening(body, iterations=2)
    body = ndimage.binary_erosion(body, iterations=3)
    if body.sum() == 0:
        return np.zeros_like(hu, dtype=np.uint8), body

    fat = body & (hu >= FAT[0]) & (hu <= FAT[1])
    soft = body & (hu >= MUSCLE[0]) & (hu <= MUSCLE[1])

    # 离体表距离
    lab, _ = ndimage.label(~body)
    outs = set(lab[e] for e in [(0, 0), (0, -1), (-1, 0), (-1, -1)] if lab[e] > 0)
    inside = ~np.isin(lab, list(outs))
    dist_surf = ndimage.distance_transform_edt(inside) * px
    can = inside & (hu > -350)

    # 皮下脂肪：沿脂肪路径与体表相连、测地膨胀<22mm
    sat = fat & (dist_surf < 5.0)
    for _ in range(int(round(SAT_MM / px))):
        sat = fat & ndimage.binary_dilation(sat)
    vat = fat & ~sat

    # 腹壁肌肉环
    d_sat = ndimage.distance_transform_edt(~sat) * px if sat.any() else np.full_like(hu, 1e9)
    wall = can & soft & (d_sat <= WALL_MM) & (dist_surf > 6.0)

    # 脊柱两侧肌肉
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
            anterior = (-dy) / norm
            front = anterior >= np.cos(np.deg2rad(50.0))
            posterior = can & soft & (d_spine <= 10.0) & (~front)
            for _ in range(int(round(40.0 / px))):
                posterior = can & soft & (~front) & ndimage.binary_dilation(posterior)
            posterior = posterior & (d_spine <= SPINE_MM)
            canal = ndimage.binary_fill_holes(bone) & ~bone

    muscle = (wall | posterior) & body & (~canal)

    label = np.zeros(hu.shape, dtype=np.uint8)
    label[sat] = 1
    label[vat] = 2
    label[muscle] = 3
    return label, body


def guess_protocol(ds):
    """粗略判断平扫/增强（原型演示用，不必精确）。"""
    text = (str(getattr(ds, "ProtocolName", "")) + " " +
            str(getattr(ds, "StudyDescription", "")) + " " +
            str(getattr(ds, "SeriesDescription", "")))
    low = text.lower()
    if any(k in text for k in ["增强", "动脉", "静脉", "门脉"]) or \
       any(k in low for k in ["+c", "contrast", "portal", "arterial", "venous"]) or \
       getattr(ds, "ContrastBolusAgent", None):
        return "腹部CT轴位 · 增强"
    return "腹部CT轴位 · 平扫"


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(CT_DIR, "*.dcm")))
    print("ct/ 中 DICOM 总数：", len(files))
    if not files:
        raise SystemExit("未找到 DICOM，请检查 ct/ 目录")

    picks = [files[i] for i in PICK_INDICES if i < len(files)]

    payload = {}
    n_ok = 0
    for k, path in enumerate(picks):
        bn = os.path.basename(path)
        try:
            hu, px, ds = read_hu(path)
            label, body = segment_v3(hu, px)
        except Exception as e:  # noqa: BLE001
            print(f"  跳过 {bn}: {e}")
            continue
        name, sex, age = DEMO_META[k % len(DEMO_META)]
        meta = {
            "id": name,
            "sex": sex,
            "age": age,
            "protocol": guess_protocol(ds),
            "manufacturer": str(getattr(ds, "Manufacturer", "") or "-"),
            "slice_thickness": str(getattr(ds, "SliceThickness", "") or "-"),
            "pixel_spacing": f"{px:.3f}",
            "src": bn,
        }
        payload[f"hu_{n_ok}"] = np.ascontiguousarray(hu, dtype=np.float32)
        payload[f"label_{n_ok}"] = np.ascontiguousarray(label, dtype=np.uint8)
        payload[f"body_{n_ok}"] = np.ascontiguousarray(body, dtype=bool)
        payload[f"px_{n_ok}"] = np.float32(px)
        payload[f"meta_{n_ok}"] = np.array(json.dumps(meta, ensure_ascii=False))
        n_ok += 1
        a = px * px / 100.0
        print(f"  [{n_ok}] {bn:16s} {meta['manufacturer'][:10]:10s} px={px:.3f}  "
              f"SAT={np.count_nonzero(label==1)*a:6.1f} VAT={np.count_nonzero(label==2)*a:6.1f} "
              f"SMA={np.count_nonzero(label==3)*a:6.1f} cm²")

    payload["n"] = np.int32(n_ok)
    np.savez_compressed(OUT_NPZ, **payload)
    print(f"\n已生成 {OUT_NPZ}（{n_ok} 例）")


if __name__ == "__main__":
    main()
