# -*- coding: utf-8 -*-
"""构建脚本：把 ct/ 里若干真实切片「烘焙」成内置示例资产 assets/sample.npz。

仅构建时运行一次。原型运行时只加载该 npz 静态资产，不读 DICOM、不跑 v3 算法。
产出每例：hu(float32)、label(uint8, 0/1/2/3)、body(bool)、px_mm(float)、匿名元数据(JSON)。

算法与读取均复用 app/ 下的正式模块（单一来源，避免口径漂移）：
    app.dicom_io.read_hu、app.segmentation.segment_v3

用法：
    "C:/Users/Levin Zhang/.workbuddy/binaries/python/envs/default/Scripts/python.exe" _make_sample.py
"""
import os
import sys
import glob
import json
import numpy as np

try:  # Windows 控制台默认 GBK，避免打印 ² 等字符报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import dicom_io          # noqa: E402
from app import segmentation      # noqa: E402

CT_DIR = os.path.join(ROOT, "ct")
ASSETS_DIR = os.path.join(ROOT, "assets")
OUT_NPZ = os.path.join(ASSETS_DIR, "sample.npz")

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


def protocol_text(meta) -> str:
    base = meta.series_desc or meta.protocol or "腹部CT轴位"
    return f"{base} · {meta.contrast}" if meta.contrast else base


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
            hu, px, dmeta = dicom_io.read_hu(path)
            label, body = segmentation.segment_v3(hu, px)
        except Exception as e:  # noqa: BLE001
            print(f"  跳过 {bn}: {e}")
            continue
        name, sex, age = DEMO_META[k % len(DEMO_META)]
        meta = {
            "id": name,
            "sex": sex,
            "age": age,
            "protocol": protocol_text(dmeta),
            "manufacturer": dmeta.manufacturer or "-",
            "slice_thickness": dmeta.slice_thickness or "-",
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
