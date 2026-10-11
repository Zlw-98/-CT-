# -*- coding: utf-8 -*-
"""单个病例的数据模型。

核心：一张 uint8 标签图（0背景/1SAT/2VAT/3SMA）——互斥语义天然成立。
auto_label 保留自动分割原始结果，用于「重置为自动」与「已编辑」标记。
"""
import numpy as np

from . import constants as C
from .undo import UndoStack


class CaseModel:
    def __init__(self, meta: dict, hu: np.ndarray, label: np.ndarray,
                 body: np.ndarray, px_mm: float):
        self.meta = dict(meta)
        self.px_mm = float(px_mm)
        self.hu = np.ascontiguousarray(hu, dtype=np.float32)
        self.body = body
        self.auto_label = np.ascontiguousarray(label, dtype=np.uint8).copy()
        self.label = self.auto_label.copy()
        self.undo = UndoStack(30)

        self.wl, self.ww = C.DEFAULT_WL
        self.visible = {C.SAT: True, C.VAT: True, C.SMA: True}
        self.opacity = dict(C.DEFAULT_OPACITY)
        self.locked = {C.SAT: False, C.VAT: False, C.SMA: False}

    # ---------- 基本信息 ----------
    @property
    def name(self) -> str:
        return self.meta.get("id", "未命名")

    @property
    def shape(self):
        return self.label.shape

    def cm2_per_px(self) -> float:
        return self.px_mm * self.px_mm / 100.0

    def subtitle(self) -> str:
        m = self.meta
        parts = [m.get("sex", ""), m.get("age", "")]
        s = " · ".join(p for p in parts if p)
        if m.get("protocol"):
            s = (s + " · " + m["protocol"]) if s else m["protocol"]
        return s

    # ---------- 面积 ----------
    def is_edited(self) -> bool:
        return bool(np.any(self.label != self.auto_label))

    def reset_to_auto(self) -> bool:
        if not self.is_edited():
            return False
        self.undo.push(self.label)
        self.label = self.auto_label.copy()
        return True

    def areas(self) -> dict:
        a = self.cm2_per_px()
        n_sat = int(np.count_nonzero(self.label == C.SAT))
        n_vat = int(np.count_nonzero(self.label == C.VAT))
        n_sma = int(np.count_nonzero(self.label == C.SMA))
        mus = self.hu[self.label == C.SMA]
        return {
            "SAT": n_sat * a,
            "VAT": n_vat * a,
            "SMA": n_sma * a,
            "fat": (n_sat + n_vat) * a,
            "vat_sat": (n_vat / n_sat) if n_sat else None,
            "muscle_hu": float(mus.mean()) if mus.size else None,
            "body": int(np.count_nonzero(self.body)) * a,
        }
