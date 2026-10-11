# -*- coding: utf-8 -*-
"""v3 阈值几何法（纯函数，无文件 IO）。

把 HU 切片自动分割为 SAT / VAT / SMA，返回单一 uint8 标签图（互斥语义天然成立）。
算法与 `_threshold_v3.py` 基线一致；参数默认值见 `constants.V3_DEFAULTS`（需求附录 A）。

骨骼肌 = 腹壁肌肉环(紧贴皮下脂肪内侧的薄层) ∪ 脊柱周围软组织(腰大肌/竖脊肌/椎旁)
内脏脂肪 = 腹壁环围成的"腹腔"内、且非皮下的脂肪
皮下脂肪 = 紧贴体表且测地膨胀 < SAT_MM 的脂肪
"""
import numpy as np
from scipy import ndimage

from . import constants as C


def default_params() -> dict:
    return dict(C.V3_DEFAULTS)


def _merge(params):
    p = default_params()
    if params:
        p.update(params)
    return p


def body_mask(hu: np.ndarray, params: dict = None) -> np.ndarray:
    """身体掩膜：HU > 阈值 → 填洞 → 开运算 → 腐蚀。返回 bool 数组。

    导入时用于即时显示"身体面积"，与 segment_v3 内部第一步完全一致。
    """
    p = _merge(params)
    hu = np.asarray(hu, dtype=np.float32)
    body = ndimage.binary_fill_holes(hu > p["body_hu"])
    body = ndimage.binary_opening(body, iterations=2)
    body = ndimage.binary_erosion(body, iterations=3)
    return body


def segment_v3(hu: np.ndarray, px_mm: float, params: dict = None):
    """v3 几何约束法。

    参数
    ----
    hu : float32 (H,W)，已做 RescaleSlope/Intercept 换算
    px_mm : 像素间距（mm/像素），面积换算与测地半径依赖它
    params : 覆盖 V3_DEFAULTS 的字典，None 用默认

    返回
    ----
    (label uint8 (H,W), body bool (H,W))
        label 取值：0 背景 / 1 SAT(皮下脂肪) / 2 VAT(内脏脂肪) / 3 SMA(骨骼肌)
    """
    p = _merge(params)
    hu = np.asarray(hu, dtype=np.float32)
    px = float(px_mm)
    if px <= 0:
        raise ValueError("像素间距必须为正数")

    body = body_mask(hu, p)
    label = np.zeros(hu.shape, dtype=np.uint8)
    if body.sum() == 0:
        return label, body

    fat = body & (hu >= p["fat_lo"]) & (hu <= p["fat_hi"])
    soft = body & (hu >= p["muscle_lo"]) & (hu <= p["muscle_hi"])

    # 离体表距离：把 ~body 的连通域分为"外部"与"体内空洞"，体内区域算距离变换
    lab, _ = ndimage.label(~body)
    outs = set(lab[e] for e in [(0, 0), (0, -1), (-1, 0), (-1, -1)] if lab[e] > 0)
    inside = ~np.isin(lab, list(outs))
    dist_surf = ndimage.distance_transform_edt(inside) * px
    can = inside & (hu > p["body_hu"])   # 体部内解剖区

    # 皮下脂肪：从紧贴体表的脂肪出发，沿脂肪路径做测地膨胀（抗脂肪环断裂）
    sat = fat & (dist_surf < 5.0)
    for _ in range(int(round(p["sat_mm"] / px))):
        sat = fat & ndimage.binary_dilation(sat)
    # 内脏脂肪：其余脂肪（与体表不相连 / 超测地距离）
    vat = fat & ~sat

    # 腹壁肌肉环：紧贴皮下脂肪内侧 WALL_MM 的软组织（排除皮肤）
    d_sat = ndimage.distance_transform_edt(~sat) * px if sat.any() else np.full_like(hu, 1e9)
    wall = can & soft & (d_sat <= p["wall_mm"]) & (dist_surf > 6.0)

    # 脊柱两侧肌肉：从椎体沿软组织洪水填充（脂肪塑形），排除正前扇区，圆盘半径封顶
    posterior = np.zeros_like(body)
    canal = np.zeros_like(body)
    bone = body & (hu > 200)
    if bone.sum() > 20:
        bl, bc = ndimage.label(bone)
        sizes = ndimage.sum(np.ones_like(bl), bl, index=range(1, bc + 1))
        if len(sizes) > 0:
            spine = (bl == (1 + int(np.argmax(sizes))))   # 最大骨块=椎体
            d_spine = ndimage.distance_transform_edt(~spine) * px
            ys, xs = np.where(spine)
            cy, cx = ys.mean(), xs.mean()
            Y, X = np.mgrid[0:hu.shape[0], 0:hu.shape[1]]
            dy, dx = (Y - cy).astype(float), (X - cx).astype(float)
            norm = np.sqrt(dx * dx + dy * dy) + 1e-6
            anterior = (-dy) / norm                          # 1 = 正前方(图像上方)
            front = anterior >= np.cos(np.deg2rad(p["front_deg"]))
            posterior = can & soft & (d_spine <= 10.0) & (~front)
            for _ in range(int(round(p["spine_grow_mm"] / px))):
                posterior = can & soft & (~front) & ndimage.binary_dilation(posterior)
            posterior = posterior & (d_spine <= p["spine_mm"])
            canal = ndimage.binary_fill_holes(bone) & ~bone   # 椎管+椎体骨髓腔

    muscle = (wall | posterior) & body & (~canal)

    label[sat] = C.SAT
    label[vat] = C.VAT
    label[muscle] = C.SMA       # 最后赋值：重叠处归 SMA，保证单一标签
    return label, body
