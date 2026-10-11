# -*- coding: utf-8 -*-
"""用户设置：v3 算法参数、默认输出目录、图层颜色。

持久化到用户配置目录的 JSON：
    %APPDATA%/腹部CT体成分分析工具/settings.json（Windows）
失败时静默回退到内置默认值（不影响运行）。
"""
import json
import os

from . import constants as C

APP_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "腹部CT体成分分析工具")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

# 设置对话框字段：(键, 中文名, 最小, 最大, 步长)
V3_FIELDS = [
    ("body_hu", "身体掩膜阈值 (HU)", -1200.0, 0.0, 10.0),
    ("fat_lo", "脂肪 HU 下限", -500.0, 0.0, 1.0),
    ("fat_hi", "脂肪 HU 上限", -200.0, 200.0, 1.0),
    ("muscle_lo", "肌肉 HU 下限", -200.0, 200.0, 1.0),
    ("muscle_hi", "肌肉 HU 上限", 0.0, 800.0, 1.0),
    ("sat_mm", "皮下脂肪厚度 SAT (mm)", 0.0, 100.0, 1.0),
    ("wall_mm", "腹壁肌厚度 WALL (mm)", 0.0, 60.0, 1.0),
    ("spine_mm", "脊柱肌圆盘半径 (mm)", 0.0, 100.0, 1.0),
    ("front_deg", "正前排除扇区 (°)", 0.0, 90.0, 1.0),
    ("spine_grow_mm", "脊柱肌生长上限 (mm)", 0.0, 150.0, 1.0),
]


def defaults() -> dict:
    return {
        "v3": dict(C.V3_DEFAULTS),
        "output_dir": "",
        "colors": {str(l): list(C.LAYER_RGB[l]) for l in C.LAYERS},
    }


def load() -> dict:
    d = defaults()
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return d

    v3 = data.get("v3")
    if isinstance(v3, dict):
        for k in d["v3"]:
            if k in v3:
                try:
                    d["v3"][k] = float(v3[k])
                except (TypeError, ValueError):
                    pass
    if isinstance(data.get("output_dir"), str):
        d["output_dir"] = data["output_dir"]
    cols = data.get("colors")
    if isinstance(cols, dict):
        for k in list(d["colors"]):
            v = cols.get(k)
            if isinstance(v, (list, tuple)) and len(v) == 3:
                try:
                    d["colors"][k] = [max(0, min(255, int(x))) for x in v]
                except (TypeError, ValueError):
                    pass
    return d


def save(d: dict) -> bool:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def reset_defaults() -> bool:
    return save(defaults())


def v3_params() -> dict:
    return load()["v3"]


def output_dir() -> str:
    return load()["output_dir"]


def colors() -> dict:
    return {int(k): tuple(v) for k, v in load()["colors"].items()}


def apply_colors():
    """把保存的颜色写回 constants，供渲染/导出/面板使用。"""
    for lbl, rgb in colors().items():
        C.LAYER_RGB[lbl] = tuple(rgb)
        C.LAYER_HEX[lbl] = "#%02X%02X%02X" % tuple(rgb)
