# -*- coding: utf-8 -*-
"""真实 DICOM 读取。

- `scan_folder` / `scan_file`：只读文件头（stop_before_pixels），快速建立病例列表；
  非 DICOM 或坏文件不抛异常，记为 `DicomMeta.error` 并跳过。
- `read_hu`：按需读取像素并做 HU 换算（RescaleSlope/Intercept）。

兼容 GE / Siemens / Philips / 联影等常见厂商：字段缺失时给出兜底值。
"""
import os
from dataclasses import dataclass

import numpy as np
import pydicom

# 递归扫描时排除的目录名（避免误入系统目录）
_SKIP_DIRS = {".git", "__pycache__", "$RECYCLE.BIN", "System Volume Information"}

_SEX_CN = {"M": "男", "F": "女", "O": "其他"}


def _clean(v):
    s = "" if v is None else str(v).strip()
    return s


def guess_contrast(ds) -> str:
    """粗略判断平扫/增强（FR-1.3 展示用，不追求精确）。"""
    text = " ".join(_clean(getattr(ds, k, "")) for k in
                    ("ProtocolName", "StudyDescription", "SeriesDescription"))
    low = text.lower()
    if any(k in text for k in ("增强", "动脉", "静脉", "门脉")) or \
       any(k in low for k in ("+c", "contrast", "portal", "arterial", "venous")) or \
       getattr(ds, "ContrastBolusAgent", None):
        return "增强"
    return "平扫"


@dataclass
class DicomMeta:
    """一个 DICOM 文件的元数据（不含像素）。"""
    path: str
    patient_id: str = ""
    sex: str = ""                 # 已转中文：男/女/其他
    age: str = ""                 # 如 056Y
    protocol: str = ""
    series_desc: str = ""
    study_desc: str = ""
    slice_thickness: str = ""
    px_mm: float = 0.0            # PixelSpacing[0]；0 表示缺失/不可算面积
    rows: int = 0
    cols: int = 0
    window_center: float = None
    window_width: float = None
    slope: float = 1.0
    intercept: float = 0.0
    manufacturer: str = ""
    contrast: str = ""
    error: str = None             # None=可读；否则为失败原因

    @property
    def ok(self) -> bool:
        """可载入显示（已成功读头）。"""
        return self.error is None

    @property
    def can_area(self) -> bool:
        """可计算面积（需要 PixelSpacing）。"""
        return self.error is None and self.px_mm > 0

    @property
    def display_name(self) -> str:
        return self.patient_id or os.path.splitext(os.path.basename(self.path))[0]


def _first_float(ds, key):
    v = getattr(ds, key, None)
    if v is None:
        return None
    try:
        if isinstance(v, (list, tuple)):
            return float(v[0])
        return float(v)
    except (TypeError, ValueError):
        return None


def _read_header(path: str) -> DicomMeta:
    """只读文件头，构造 DicomMeta（失败时 error 非空）。"""
    try:
        ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
    except Exception as e:  # noqa: BLE001
        return DicomMeta(path=path, error=f"读取失败：{e}")

    if not getattr(ds, "SOPClassUID", None) and not getattr(ds, "Modality", None):
        return DicomMeta(path=path, error="非 DICOM 文件")

    ps = getattr(ds, "PixelSpacing", None)
    px_mm = 0.0
    if ps:
        try:
            px_mm = float(ps[0])
        except (TypeError, ValueError, IndexError):
            px_mm = 0.0

    sex_raw = _clean(getattr(ds, "PatientSex", "")).upper()[:1]
    meta = DicomMeta(
        path=path,
        patient_id=_clean(getattr(ds, "PatientID", "")),
        sex=_SEX_CN.get(sex_raw, ""),
        age=_clean(getattr(ds, "PatientAge", "")),
        protocol=_clean(getattr(ds, "ProtocolName", "")),
        series_desc=_clean(getattr(ds, "SeriesDescription", "")),
        study_desc=_clean(getattr(ds, "StudyDescription", "")),
        slice_thickness=_clean(getattr(ds, "SliceThickness", "")),
        px_mm=px_mm,
        rows=int(getattr(ds, "Rows", 0) or 0),
        cols=int(getattr(ds, "Columns", 0) or 0),
        window_center=_first_float(ds, "WindowCenter"),
        window_width=_first_float(ds, "WindowWidth"),
        slope=float(getattr(ds, "RescaleSlope", 1) or 1),
        intercept=float(getattr(ds, "RescaleIntercept", 0) or 0),
        manufacturer=_clean(getattr(ds, "Manufacturer", "")),
        contrast=guess_contrast(ds),
    )
    return meta


def _iter_dicom_files(dirpath: str, recursive: bool = True):
    if recursive:
        for root, dirs, files in os.walk(dirpath):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fn in files:
                yield os.path.join(root, fn)
    else:
        for fn in os.listdir(dirpath):
            p = os.path.join(dirpath, fn)
            if os.path.isfile(p):
                yield p


def scan_folder(dirpath: str, recursive: bool = True) -> list:
    """递归扫描文件夹，返回 DicomMeta 列表（保持自然文件名顺序）。

    非 DICOM / 坏文件保留在结果中并带 error 字段，由调用方决定是否展示。
    """
    if not os.path.isdir(dirpath):
        raise NotADirectoryError(f"不是文件夹：{dirpath}")
    metas = []
    for p in _iter_dicom_files(dirpath, recursive):
        if os.path.basename(p).startswith("."):
            continue
        metas.append(_read_header(p))
    # 过滤纯非 DICOM（error 且不是"读取失败"）——它们通常不是影像文件
    keep = [m for m in metas if m.ok or m.error != "非 DICOM 文件"]
    keep.sort(key=lambda m: (m.patient_id or "", os.path.basename(m.path)))
    return keep


def scan_file(path: str) -> DicomMeta:
    """读取单个 DICOM 文件头。"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"文件不存在：{path}")
    return _read_header(path)


def read_hu(path: str):
    """按需读取像素并换算 HU。

    返回 (hu float32 (H,W), px_mm float, DicomMeta)。
    缺失 PixelSpacing 时抛 ValueError（该文件无法计算面积）。
    """
    meta = _read_header(path)
    if not meta.ok:
        raise ValueError(meta.error or "无法读取 DICOM")
    ds = pydicom.dcmread(path, force=True)
    arr = ds.pixel_array.astype(np.float32)
    if arr.ndim == 3:
        if arr.shape[0] == 1:
            arr = arr[0]
        else:
            raise ValueError(f"不支持多层/多帧像素（shape={arr.shape}）")
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    hu = np.ascontiguousarray(arr * slope + intercept, dtype=np.float32)

    px = meta.px_mm
    if px <= 0:
        raise ValueError("缺少 PixelSpacing，无法计算面积")
    return hu, px, meta


def read_hu_from_meta(meta: DicomMeta):
    """便于闭包：给定已扫描的 meta 读像素。"""
    return read_hu(meta.path)
