# -*- coding: utf-8 -*-
"""渲染：把 HU 灰度窗与标签图叠加层转成可直接绘制的图像缓冲。

- build_gray：HU + 窗宽窗位 -> 8 位灰度 (uint8, H×W)，约 1ms。
- build_overlay：标签图 -> RGBA (uint8, H×W×4)，约 4ms。
- *_to_qimage：numpy -> QImage（内部 .copy()，避免 numpy 缓冲被回收后悬空）。
"""
import numpy as np
from PySide6.QtGui import QImage

from . import constants as C


def build_gray(hu: np.ndarray, wl: float, ww: float) -> np.ndarray:
    ww = max(1.0, float(ww))
    lo = float(wl) - ww / 2.0
    g = (hu - lo) * (255.0 / ww)
    return np.clip(g, 0, 255).astype(np.uint8)


def build_overlay(label: np.ndarray, visible: dict, rgb: dict, opacity: dict,
                  out: np.ndarray | None = None) -> np.ndarray:
    h, w = label.shape
    if out is None or out.shape != (h, w, 4):
        out = np.zeros((h, w, 4), np.uint8)
    else:
        out[...] = 0
    for lbl in C.LAYERS:
        if not visible.get(lbl, True):
            continue
        m = label == lbl
        if not m.any():
            continue
        r, g, b = rgb[lbl]
        out[m, 0] = r
        out[m, 1] = g
        out[m, 2] = b
        out[m, 3] = int(round(opacity[lbl] * 255))
    return out


def gray_to_qimage(gray_u8: np.ndarray) -> QImage:
    a = np.ascontiguousarray(gray_u8)
    h, w = a.shape
    return QImage(a.data, w, h, w, QImage.Format.Format_Grayscale8).copy()


def overlay_to_qimage(rgba: np.ndarray) -> QImage:
    a = np.ascontiguousarray(rgba)
    h, w, _ = a.shape
    return QImage(a.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
