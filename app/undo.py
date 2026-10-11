# -*- coding: utf-8 -*-
"""撤销/重做栈（快照式）。

对 512×512 uint8 标签图，每步快照 256KB，保留 30 步约 8MB，足够且实现简单。
"""
import numpy as np


class UndoStack:
    def __init__(self, limit: int = 30):
        self._past = []
        self._future = []
        self._limit = limit

    def reset(self) -> None:
        self._past.clear()
        self._future.clear()

    def can_undo(self) -> bool:
        return bool(self._past)

    def can_redo(self) -> bool:
        return bool(self._future)

    def push(self, current: np.ndarray) -> None:
        """在改动标签图 *之前* 调用，记录当前状态。"""
        self._past.append(current.copy())
        if len(self._past) > self._limit:
            self._past.pop(0)
        self._future.clear()

    def undo(self, current: np.ndarray):
        if not self._past:
            return None
        self._future.append(current.copy())
        return self._past.pop()

    def redo(self, current: np.ndarray):
        if not self._future:
            return None
        self._past.append(current.copy())
        return self._future.pop()
