# -*- coding: utf-8 -*-
"""开发自检：验证编辑/撤销/区域生长/互斥语义（离屏，不弹窗）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
from PySide6.QtWidgets import QApplication

from app.sample_data import load_sample_cases
from app import constants as C
from ui.image_view import ImageView


def overlap_count(label):
    s = np.stack([label == C.SAT, label == C.VAT, label == C.SMA])
    return int((s.sum(0) > 1).sum())


def main():
    cases = load_sample_cases()
    print(f"病例数：{len(cases)}")
    case = cases[0]
    a0 = case.areas()
    print(f"初始面积： SAT={a0['SAT']:.1f} VAT={a0['VAT']:.1f} SMA={a0['SMA']:.1f} "
          f"总脂肪={a0['fat']:.1f} VAT/SAT={a0['vat_sat']:.2f} 肌肉HU={a0['muscle_hu']:.1f}")
    print("初始重叠像素：", overlap_count(case.label), "（应为 0）")
    assert overlap_count(case.label) == 0

    app = QApplication(sys.argv)
    v = ImageView()
    v.set_case(case)
    v.set_target_layer(C.SMA)
    v.grow_restrict = True
    v.grow_radius_mm = 24.0
    v.grow_conn = 8
    v.grow_lo, v.grow_hi = C.LAYER_HU[C.SMA]

    ys, xs = np.where(case.label == C.SMA)
    sy, sx = int(ys[len(ys) // 2]), int(xs[len(xs) // 2])
    before = int(np.count_nonzero(case.label == C.SMA))
    v._apply_grow(sx, sy)          # (col, row)
    after = int(np.count_nonzero(case.label == C.SMA))
    print(f"区域生长(种子在SMA)：SMA {before} -> {after} 像素；重叠={overlap_count(case.label)}")
    assert overlap_count(case.label) == 0

    # 撤销
    st = case.undo.undo(case.label)
    case.label = st
    print("撤销后 SMA 像素：", int(np.count_nonzero(case.label == C.SMA)), "（应回到", before, "）")
    assert int(np.count_nonzero(case.label == C.SMA)) == before

    # 画笔：在 VAT 区域涂 SAT，应自动从 VAT 扣掉（互斥）
    v.tool = C.TOOL_BRUSH
    v.brush_mm = 30.0
    vy, vx = np.where(case.label == C.VAT)
    cy, cx = int(vy[len(vy) // 2]), int(vx[len(vx) // 2])
    v.set_target_layer(C.SAT)
    vat_before = int(np.count_nonzero(case.label == C.VAT))
    sat_before = int(np.count_nonzero(case.label == C.SAT))
    v._begin_paint(cx, cy, erase=False)
    vat_after = int(np.count_nonzero(case.label == C.VAT))
    sat_after = int(np.count_nonzero(case.label == C.SAT))
    print(f"画笔涂SAT：SAT {sat_before}->{sat_after}，VAT {vat_before}->{vat_after}"
          f"（VAT 应减少）；重叠={overlap_count(case.label)}")
    assert overlap_count(case.label) == 0
    assert sat_after > sat_before and vat_after < vat_before

    # 重置为自动
    case.reset_to_auto()
    print("重置后重叠：", overlap_count(case.label),
          "；SMA=", int(np.count_nonzero(case.label == C.SMA)))
    assert int(np.count_nonzero(case.label == C.SMA)) == before
    print("\n全部断言通过 ✓")


if __name__ == "__main__":
    main()
