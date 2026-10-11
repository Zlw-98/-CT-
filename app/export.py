# -*- coding: utf-8 -*-
"""结果导出：数据表 CSV 与叠加分割图 PNG。

- `export_csv`：UTF-8 with BOM（Excel 中文不乱码），通用列，多例为多行表。
- `export_overlay_png`：把灰度 CT + 三层半透明叠加合成一张图，附颜色图例与面积数值。
颜色来源于 `render.build_overlay`，与屏幕显示口径一致。
"""
import csv
import os

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen

from . import constants as C
from . import render

# 通用导出列（FR-6.1）
CSV_COLUMNS = [
    "文件", "患者ID", "性别", "年龄", "序列描述", "层厚mm", "像素间距mm",
    "身体面积cm²", "总脂肪cm²", "皮下脂肪SATcm²", "内脏脂肪VATcm²", "骨骼肌SMAcm²",
    "VAT/SAT", "肌肉平均HU", "是否人工编辑",
]


def case_row(case) -> dict:
    """把一个病例的元数据与面积整理成一行。"""
    case.ensure_loaded()
    a = case.areas()
    m = case.meta
    return {
        "文件": m.get("src", ""),
        "患者ID": case.name,
        "性别": m.get("sex", ""),
        "年龄": m.get("age", ""),
        "序列描述": m.get("protocol", ""),
        "层厚mm": m.get("slice_thickness", ""),
        "像素间距mm": f"{case.px_mm:.3f}" if case.px_mm else "",
        "身体面积cm²": f"{a['body']:.1f}",
        "总脂肪cm²": f"{a['fat']:.1f}",
        "皮下脂肪SATcm²": f"{a['SAT']:.1f}",
        "内脏脂肪VATcm²": f"{a['VAT']:.1f}",
        "骨骼肌SMAcm²": f"{a['SMA']:.1f}",
        "VAT/SAT": "" if a["vat_sat"] is None else f"{a['vat_sat']:.2f}",
        "肌肉平均HU": "" if a["muscle_hu"] is None else f"{a['muscle_hu']:.1f}",
        "是否人工编辑": "是" if case.is_edited() else "否",
    }


def export_csv(cases, path: str) -> int:
    """写出 CSV，返回写出的行数。"""
    rows = [case_row(c) for c in cases]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------- PNG
def export_overlay_png(case, path: str):
    """合成叠加图 PNG：灰度 CT + 三层彩色叠加 + 图例与面积数值。"""
    case.ensure_loaded()
    hu = case.hu
    h, w = hu.shape

    gray = render.gray_to_qimage(render.build_gray(hu, case.wl, case.ww))
    # 导出时三层一律可见，避免受界面开关影响
    rgba = render.build_overlay(
        case.label, {l: True for l in C.LAYERS}, C.LAYER_RGB,
        C.DEFAULT_OPACITY)
    overlay = render.overlay_to_qimage(rgba)

    pad, panel_w, title_h = 16, 300, 40
    canvas_w = pad * 3 + w + panel_w
    canvas_h = max(h + title_h + pad * 2, 320)
    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_RGB32)
    canvas.fill(QColor("#FFFFFF"))

    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    # 标题
    p.setPen(QColor("#1A2230"))
    p.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
    p.drawText(pad, pad + 22, f"{case.name} · {case.subtitle()}")

    # 图像
    ix, iy = pad, pad + title_h
    p.drawImage(ix, iy, gray)
    p.drawImage(ix, iy, overlay)
    p.setPen(QPen(QColor("#C8D0DC")))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(ix - 1, iy - 1, w + 1, h + 1)

    _draw_legend(p, case, ix + w + pad, iy)
    p.end()
    canvas.save(path)


def _draw_legend(p: QPainter, case, lx: int, ly: int):
    a = case.areas()
    p.setPen(QColor("#5A6678"))
    p.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
    p.drawText(lx, ly + 4, "图层 / 面积")
    y = ly + 34

    rows = [(C.SAT, "皮下脂肪 SAT", a["SAT"]),
            (C.VAT, "内脏脂肪 VAT", a["VAT"]),
            (C.SMA, "骨骼肌 SMA", a["SMA"])]
    for lbl, name, val in rows:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C.LAYER_HEX[lbl]))
        p.drawRoundedRect(lx, y - 12, 14, 14, 3, 3)
        p.setPen(QColor("#1A2230"))
        p.setFont(QFont("Microsoft YaHei", 10))
        p.drawText(lx + 22, y, name)
        p.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        p.drawText(lx + 22, y + 20, f"{val:.1f} cm²")
        y += 50

    # 派生指标
    y += 4
    p.setPen(QColor("#8A94A6"))
    p.setFont(QFont("Microsoft YaHei", 9))
    metrics = [
        f"总脂肪 {a['fat']:.1f} cm²",
        "VAT/SAT " + ("—" if a["vat_sat"] is None else f"{a['vat_sat']:.2f}"),
        "肌肉平均HU " + ("—" if a["muscle_hu"] is None else f"{a['muscle_hu']:.1f}"),
        f"身体面积 {a['body']:.1f} cm²",
        "状态 " + ("已人工微调" if case.is_edited() else "自动结果"),
    ]
    for t in metrics:
        p.drawText(lx, y, t)
        y += 18
