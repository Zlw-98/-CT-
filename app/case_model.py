# -*- coding: utf-8 -*-
"""单个病例的数据模型。

核心：一张 uint8 标签图（0背景/1SAT/2VAT/3SMA）——互斥语义天然成立。
auto_label 保留自动分割原始结果，用于「重置为自动」与「已编辑」标记。

支持**懒加载**：真实导入时先用文件头建立列表，像素在首次显示时（`ensure_loaded`）才读取，
避免一次导入几十例时全部解压像素。内置示例数据在构造时即已加载。
"""
import os

import numpy as np

from . import constants as C
from . import segmentation
from .undo import UndoStack


class CaseModel:
    def __init__(self, meta: dict, hu: np.ndarray = None, label: np.ndarray = None,
                 body: np.ndarray = None, px_mm: float = 0.0, loader=None):
        self.meta = dict(meta)
        self.px_mm = float(px_mm) if px_mm else 0.0
        self.hu = hu
        self.body = body
        self._loader = loader            # 无参可调用 -> (hu, px_mm, meta)
        self._loaded = hu is not None

        if self._loaded:
            self.hu = np.ascontiguousarray(hu, dtype=np.float32)
            self.body = body
            self.auto_label = np.ascontiguousarray(label, dtype=np.uint8).copy()
            self.label = self.auto_label.copy()
        else:
            self.auto_label = None
            self.label = None

        self.undo = UndoStack(30)

        self.wl, self.ww = C.DEFAULT_WL
        self.visible = {C.SAT: True, C.VAT: True, C.SMA: True}
        self.opacity = dict(C.DEFAULT_OPACITY)
        self.locked = {C.SAT: False, C.VAT: False, C.SMA: False}

    # ---------- 构造 ----------
    @classmethod
    def from_dicom(cls, meta) -> "CaseModel":
        """由已扫描的 DicomMeta 建立懒加载病例（像素在首次显示时读取）。"""
        def loader(_m=meta):
            from . import dicom_io
            return dicom_io.read_hu(_m.path)

        display = {
            "id": meta.display_name,
            "sex": meta.sex,
            "age": meta.age,
            "protocol": _protocol_text(meta),
            "manufacturer": meta.manufacturer or "-",
            "slice_thickness": meta.slice_thickness or "-",
            "pixel_spacing": f"{meta.px_mm:.3f}" if meta.px_mm else "-",
            "contrast": meta.contrast,
            "src": os.path.basename(meta.path),
            "path": meta.path,
        }
        return cls(meta=display, px_mm=meta.px_mm, loader=loader)

    # ---------- 懒加载 ----------
    def ensure_loaded(self):
        """首次访问像素时读取并补齐 body / label / auto_label。"""
        if self._loaded:
            return
        if self._loader is None:
            raise RuntimeError(f"病例 {self.name} 无像素加载器")
        hu, px_mm, _meta = self._loader()
        self.hu = np.ascontiguousarray(hu, dtype=np.float32)
        self.px_mm = float(px_mm)
        from . import settings
        self.body = segmentation.body_mask(self.hu, settings.v3_params())
        self.auto_label = np.zeros(self.hu.shape, dtype=np.uint8)
        self.label = self.auto_label.copy()
        self._loaded = True

    @property
    def loaded(self) -> bool:
        return self._loaded

    def apply_segmentation(self, hu, label, body):
        """用于批量分割回填：一次性写入 hu/body/auto_label/label 并清空撤销栈。"""
        self.hu = np.ascontiguousarray(hu, dtype=np.float32)
        self.body = body
        self.auto_label = np.ascontiguousarray(label, dtype=np.uint8).copy()
        self.label = self.auto_label.copy()
        self._loaded = True
        self.undo.reset()

    # ---------- 基本信息 ----------
    @property
    def name(self) -> str:
        return self.meta.get("id", "未命名")

    @property
    def shape(self):
        self.ensure_loaded()
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
        self.ensure_loaded()
        return bool(np.any(self.label != self.auto_label))

    def reset_to_auto(self) -> bool:
        self.ensure_loaded()
        if not self.is_edited():
            return False
        self.undo.push(self.label)
        self.label = self.auto_label.copy()
        return True

    def areas(self) -> dict:
        self.ensure_loaded()
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


def _protocol_text(meta) -> str:
    """拼一句展示用序列描述：如「腹部CT轴位 · 平扫」。"""
    base = meta.protocol or meta.series_desc or "CT"
    if meta.contrast:
        base = f"{base} · {meta.contrast}"
    return base
