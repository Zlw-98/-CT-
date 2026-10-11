# -*- coding: utf-8 -*-
"""图像编辑：画笔/橡皮（圆盘涂抹）与区域生长。全部就地修改标签图（覆盖语义）。"""
import numpy as np
from scipy import ndimage


def disk_mask(shape, cy: int, cx: int, r: float) -> np.ndarray:
    """布尔圆盘掩膜，半径 r（图像像素）。"""
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r


def paint_disk(label: np.ndarray, cy: int, cx: int, r: float, target: int,
               allow: np.ndarray | None = None) -> None:
    """把圆盘内像素赋给目标层（自动从其它层扣掉——单一标签图天然互斥）。

    allow：可选的布尔掩膜（如 HU 范围内像素），只在该区域内涂抹。
    """
    m = disk_mask(label.shape, cy, cx, r)
    if allow is not None:
        m &= allow
    label[m] = target


def erase_disk(label: np.ndarray, cy: int, cx: int, r: float,
               allow: np.ndarray | None = None) -> None:
    """把圆盘内像素擦回背景；allow 同上，限制擦除范围。"""
    m = disk_mask(label.shape, cy, cx, r)
    if allow is not None:
        m &= allow
    label[m] = 0


def grow_selection(hu: np.ndarray, body: np.ndarray, seed_yx, lo: float, hi: float,
                   conn: int = 8, restrict_body: bool = True,
                   radius_mm: float = 0.0, px_mm: float = 1.0):
    """区域生长：返回与种子点连通的候选区布尔掩膜；种子不可用时返回 None。

    候选 = (lo ≤ HU ≤ hi) ∩ body ∩ (以种子为中心、radius_mm 的圆盘)。
    用 ndimage.label 取种子所在连通域，约 1ms。
    """
    sy, sx = int(seed_yx[0]), int(seed_yx[1])
    h, w = hu.shape
    if not (0 <= sy < h and 0 <= sx < w):
        return None
    cand = (hu >= lo) & (hu <= hi)
    if restrict_body:
        cand &= body
    if radius_mm and radius_mm > 0:
        cand &= disk_mask(hu.shape, sy, sx, radius_mm / px_mm)
    if not cand[sy, sx]:
        return None
    struct = ndimage.generate_binary_structure(2, 2 if conn == 8 else 1)
    lab, _ = ndimage.label(cand, structure=struct)
    return lab == lab[sy, sx]
