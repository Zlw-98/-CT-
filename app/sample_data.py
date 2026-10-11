# -*- coding: utf-8 -*-
"""加载内置示例数据（assets/sample.npz，由 _make_sample.py 构建）。

原型阶段不读真实 DICOM、不跑实时算法——只加载这份静态资产。
"""
import os
import sys
import json
import numpy as np

from .case_model import CaseModel


def assets_path() -> str:
    # 打包（PyInstaller）后资源解压到 sys._MEIPASS；开发时用项目根目录
    if getattr(sys, "frozen", False):
        root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", "sample.npz")


def load_sample_cases() -> list:
    path = assets_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"缺少内置示例数据：{path}\n请先运行 _make_sample.py 生成。")
    data = np.load(path, allow_pickle=False)
    n = int(data["n"])
    cases = []
    for i in range(n):
        meta = json.loads(str(data[f"meta_{i}"]))
        cases.append(CaseModel(
            meta=meta,
            hu=data[f"hu_{i}"],
            label=data[f"label_{i}"],
            body=data[f"body_{i}"],
            px_mm=float(data[f"px_{i}"]),
        ))
    return cases
