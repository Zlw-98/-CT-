# -*- coding: utf-8 -*-
"""批量自动分割的后台工作器（放进 QThread 运行，避免冻结界面）。

约束：worker 不触碰任何控件；用 `Signal(object)` 传 numpy；结果凭 key（文件路径）回填。
取消：主线程调用 `QThread.requestInterruption()`，worker 在循环中检查中断标志。
"""
from PySide6.QtCore import QObject, Signal, Slot, QThread

from . import dicom_io
from . import segmentation


class SegmentWorker(QObject):
    progress = Signal(int, int, str)          # done, total, key
    one_done = Signal(str, object, object, object)  # key, hu, label, body
    one_failed = Signal(str, str)             # key, error
    all_done = Signal(int, int)               # ok, failed

    def __init__(self, jobs):
        """jobs: list[(key, path)]，key 通常为文件路径（回填用）。"""
        super().__init__()
        self.jobs = list(jobs)

    @Slot()
    def run(self):
        ok = failed = 0
        total = len(self.jobs)
        for i, (key, path) in enumerate(self.jobs):
            if QThread.currentThread().isInterruptionRequested():
                break
            try:
                hu, px_mm, _meta = dicom_io.read_hu(path)
                label, body = segmentation.segment_v3(hu, px_mm)
                self.one_done.emit(key, hu, label, body)
                ok += 1
            except Exception as e:  # noqa: BLE001
                self.one_failed.emit(key, str(e))
                failed += 1
            self.progress.emit(i + 1, total, key)
        self.all_done.emit(ok, failed)
