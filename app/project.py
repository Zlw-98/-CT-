# -*- coding: utf-8 -*-
"""工程文件 `.bcprj`：保存/载入病例列表、人工标注与视图状态，实现可复现（FR-7）。

格式（zip，deflate）：
    project.json         # 病例列表 / 参数 / 视图状态 / 当前单元
    masks/<cid>.npz      # hu(int16 或 float32) + label + auto_label

HU 为整数且在 int16 范围内时以 int16 存储（体积减半），否则 float32。
body 掩膜不存储，载入时由 HU 重算（确定性，见 segmentation.body_mask）。
"""
import io
import json
import zipfile

import numpy as np

from . import constants as C
from . import segmentation
from .case_model import CaseModel

FORMAT = "bcprj"
VERSION = 1


def _int_keys(d):
    """JSON 的键是字符串，转回 int（标签枚举）。"""
    return {int(k): v for k, v in d.items()}


def save_project(path: str, cases, current_index: int = 0, view_state: dict = None):
    """把病例列表与标注写入 .bcprj。"""
    view_state = view_state or {}
    meta_list = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, c in enumerate(cases):
            c.ensure_loaded()
            cid = f"case_{i}"
            meta_list.append({
                "cid": cid,
                "meta": c.meta,
                "px_mm": c.px_mm,
                "wl": c.wl,
                "ww": c.ww,
                "visible": {str(k): v for k, v in c.visible.items()},
                "opacity": {str(k): v for k, v in c.opacity.items()},
                "locked": {str(k): v for k, v in c.locked.items()},
            })
            z.writestr(f"masks/{cid}.npz", _pack_case(c))
        z.writestr("project.json", json.dumps({
            "format": FORMAT,
            "version": VERSION,
            "current_index": int(current_index),
            "view_state": view_state,
            "cases": meta_list,
        }, ensure_ascii=False, indent=2))
    return len(cases)


def _pack_case(c) -> bytes:
    hu = c.hu
    integral = bool(np.all(hu == np.round(hu))) if hu.size else True
    in_range = bool(hu.min() >= -32768 and hu.max() <= 32767) if hu.size else True
    if integral and in_range:
        hu_arr = np.round(hu).astype(np.int16)
    else:
        hu_arr = hu.astype(np.float32)
    buf = io.BytesIO()
    np.savez_compressed(buf, hu=hu_arr,
                        label=np.ascontiguousarray(c.label, dtype=np.uint8),
                        auto_label=np.ascontiguousarray(c.auto_label, dtype=np.uint8))
    return buf.getvalue()


def load_project(path: str):
    """载入 .bcprj，返回 (cases, current_index, view_state)。"""
    with zipfile.ZipFile(path, "r") as z:
        proj = json.loads(z.read("project.json").decode("utf-8"))
        if proj.get("format") != FORMAT:
            raise ValueError("不是本程序的工程文件")
        cases = []
        for cm in proj["cases"]:
            cid = cm["cid"]
            with z.open(f"masks/{cid}.npz") as f:
                d = np.load(io.BytesIO(f.read()), allow_pickle=False)
                hu = d["hu"].astype(np.float32)
                label = d["label"]
                auto = d["auto_label"]
            body = segmentation.body_mask(hu)
            c = CaseModel(meta=cm["meta"], hu=hu, label=auto, body=body,
                          px_mm=cm.get("px_mm", 0.0))
            c.auto_label = np.ascontiguousarray(auto, dtype=np.uint8).copy()
            c.label = np.ascontiguousarray(label, dtype=np.uint8).copy()
            c.wl = float(cm.get("wl", C.DEFAULT_WL[0]))
            c.ww = float(cm.get("ww", C.DEFAULT_WL[1]))
            c.visible = _int_keys(cm.get("visible", {})) or dict(c.visible)
            c.opacity = _int_keys(cm.get("opacity", {})) or dict(c.opacity)
            c.locked = _int_keys(cm.get("locked", {})) or dict(c.locked)
            c.undo.reset()
            cases.append(c)
    return cases, int(proj.get("current_index", 0)), proj.get("view_state", {})
