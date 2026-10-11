# -*- coding: utf-8 -*-
"""图像显示与交互控件（自绘 QWidget）。

- 显示：灰度 CT + 半透明彩色叠加（最近邻，编辑所见即所得）。
- 视图：滚轮缩放（以光标为锚）、中/右键平移、拖拽调窗宽窗位。
- 工具：窗宽窗位 / 区域生长 / 画笔 / 橡皮（左键按当前工具派发）。
- 状态：hovered 信号上报光标处坐标与 HU。
"""
import math

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QSizePolicy

from app import constants as C
from app import render
from app import editing


class ImageView(QWidget):
    hovered = Signal(int, int, float)      # col, row, hu
    edited = Signal()                      # 标签被修改
    wlChanged = Signal(int, int)           # wl, ww

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        self.case = None
        self._gray_qimg = None
        self._ov_rgba = None
        self._ov_qimg = None

        # 视图变换（屏幕坐标）
        self._zoom = 1.0          # 屏幕像素 / 毫米
        self._sx = 1.0            # 屏幕像素 / 图像列
        self._sy = 1.0            # 屏幕像素 / 图像行
        self._ox = 0.0
        self._oy = 0.0
        self._autofit = True

        # 工具状态
        self.tool = C.TOOL_WL
        self.target_layer = C.SMA
        self.brush_mm = 8.0
        self.brush_limit_hu = True      # 画笔/橡皮是否按 HU 范围限制
        self.hu_lo, self.hu_hi = C.LAYER_HU[C.SMA]
        self.grow_radius_mm = 24.0
        self.grow_conn = 8
        self.grow_restrict = True

        # 交互临时状态
        self._drag = None          # 'pan' | 'wl' | 'paint' | 'erase'
        self._drag_start = None
        self._wl0 = None
        self._last_paint = None
        self._cursor_pos = None
        self._stroke_allow = None

        self._update_cursor()

    # ==================== 数据接口 ====================
    def set_case(self, case):
        self.case = case
        if case is not None:
            case.ensure_loaded()
        self.rebuild_gray()
        self.rebuild_overlay()
        self._autofit = True
        self._cursor_pos = None
        self.update()

    def rebuild_gray(self):
        if self.case is None:
            return
        gray = render.build_gray(self.case.hu, self.case.wl, self.case.ww)
        self._gray_qimg = render.gray_to_qimage(gray)

    def rebuild_overlay(self):
        if self.case is None:
            return
        self._ov_rgba = render.build_overlay(
            self.case.label, self.case.visible, C.LAYER_RGB,
            self.case.opacity, self._ov_rgba)
        self._ov_qimg = render.overlay_to_qimage(self._ov_rgba)

    # ==================== 视图操作 ====================
    def fit_to_window(self):
        self._autofit = True
        self._fit()
        self.update()

    def _fit(self):
        if self.case is None or self.width() <= 1 or self.height() <= 1:
            return
        h, w = self.case.shape
        px = self.case.px_mm
        z = min(self.width() / (w * px), self.height() / (h * px))
        z = max(C.ZOOM_MIN, min(C.ZOOM_MAX, z))
        self._zoom = z
        self._sx = px * z
        self._sy = px * z
        self._ox = (self.width() - w * self._sx) / 2.0
        self._oy = (self.height() - h * self._sy) / 2.0

    def _to_image(self, pos: QPointF):
        if self.case is None or self._sx <= 0 or self._sy <= 0:
            return None
        col = math.floor((pos.x() - self._ox) / self._sx)
        row = math.floor((pos.y() - self._oy) / self._sy)
        h, w = self.case.shape
        if 0 <= row < h and 0 <= col < w:
            return col, row
        return None

    def set_window(self, wl, ww):
        if self.case is None:
            return
        self.case.wl = float(wl)
        self.case.ww = float(ww)
        self.rebuild_gray()
        self.update()
        self.wlChanged.emit(int(wl), int(ww))

    def zoom_by(self, factor):
        """以视图中心为锚点缩放（供菜单调用）。"""
        if self.case is None:
            return
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        new = max(C.ZOOM_MIN, min(C.ZOOM_MAX, self._zoom * factor))
        if abs(new - self._zoom) < 1e-9:
            return
        z = new / self._zoom
        self._ox = c.x() - (c.x() - self._ox) * z
        self._oy = c.y() - (c.y() - self._oy) * z
        self._sx *= z
        self._sy *= z
        self._zoom = new
        self._autofit = False
        self.update()

    # ==================== 工具设置 ====================
    def set_tool(self, tool):
        self.tool = tool
        self._update_cursor()
        self.update()

    def set_target_layer(self, lbl):
        self.target_layer = lbl
        self.hu_lo, self.hu_hi = C.LAYER_HU[lbl]

    def set_brush_mm(self, mm):
        self.brush_mm = float(mm)
        self.update()

    def set_brush_limit_hu(self, flag):
        self.brush_limit_hu = bool(flag)

    def set_hu_range(self, lo, hi):
        self.hu_lo, self.hu_hi = float(lo), float(hi)

    def set_grow_radius(self, mm):
        self.grow_radius_mm = float(mm)

    def set_grow_conn(self, conn):
        self.grow_conn = int(conn)

    def set_grow_restrict(self, flag):
        self.grow_restrict = bool(flag)

    # ==================== 绘制 ====================
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#0E1116"))

        if self.case is None or self._gray_qimg is None:
            p.setPen(QColor("#3A4150"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "请从左侧选择病例")
            return

        h, w = self.case.shape
        target = QRectF(self._ox, self._oy, w * self._sx, h * self._sy)
        p.drawImage(target, self._gray_qimg)
        p.drawImage(target, self._ov_qimg)

        # 画笔/橡皮光标圆
        if self.tool in (C.TOOL_BRUSH, C.TOOL_ERASER) and self._cursor_pos is not None:
            r = self.brush_mm * self._zoom
            col = QColor("#FFFFFF") if self.tool == C.TOOL_BRUSH else QColor("#FF9090")
            p.setPen(QPen(col, 1, Qt.PenStyle.DashLine))
            p.drawEllipse(self._cursor_pos, r, r)

        self._draw_scalebar(p)
        p.setPen(QColor("#2A3140"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _draw_scalebar(self, p: QPainter):
        if self._zoom <= 0:
            return
        target_px = 96.0
        mm = target_px / self._zoom
        for cand in (5, 10, 20, 30, 50, 100, 200, 500):
            if cand >= mm:
                mm = float(cand)
                break
        length = mm * self._zoom
        x = self.width() - length - 20
        y = self.height() - 22
        p.setPen(QPen(QColor("#FFFFFF"), 3))
        p.drawLine(int(x), int(y), int(x + length), int(y))
        p.drawLine(int(x), int(y), int(x), int(y - 6))
        p.drawLine(int(x + length), int(y), int(x + length), int(y - 6))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(int(x), int(y - 10), f"{mm:.0f} mm")

    # ==================== 事件 ====================
    def resizeEvent(self, event):
        if self._autofit:
            self._fit()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        if self.case is None:
            return
        delta = event.angleDelta().y()
        if not delta:
            return
        pos = event.position()
        factor = 1.1 ** (delta / 120.0)
        new = max(C.ZOOM_MIN, min(C.ZOOM_MAX, self._zoom * factor))
        if abs(new - self._zoom) < 1e-9:
            return
        z = new / self._zoom
        self._ox = pos.x() - (pos.x() - self._ox) * z
        self._oy = pos.y() - (pos.y() - self._oy) * z
        self._sx *= z
        self._sy *= z
        self._zoom = new
        self._autofit = False
        self.update()

    def mousePressEvent(self, event):
        if self.case is None:
            return
        pos = event.position()
        btn = event.button()
        if btn in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._drag = "pan"
            self._drag_start = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if btn != Qt.MouseButton.LeftButton:
            return
        img = self._to_image(pos)
        if img is None:
            return
        col, row = img
        if self.tool == C.TOOL_WL:
            self._drag = "wl"
            self._drag_start = pos
            self._wl0 = (self.case.wl, self.case.ww)
        elif self.tool == C.TOOL_GROW:
            self._apply_grow(col, row)
        elif self.tool == C.TOOL_BRUSH:
            self._begin_paint(col, row, erase=False)
        elif self.tool == C.TOOL_ERASER:
            self._begin_paint(col, row, erase=True)

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._cursor_pos = pos
        if self.case is None:
            return

        if self._drag == "pan":
            d = pos - self._drag_start
            self._ox += d.x()
            self._oy += d.y()
            self._drag_start = pos
            self.update()
            return

        if self._drag == "wl":
            d = pos - self._drag_start
            wl0, ww0 = self._wl0
            ww = max(1.0, ww0 + d.x() * 2.0)
            wl = wl0 - d.y() * 2.0
            self.set_window(wl, ww)
            return

        img = self._to_image(pos)
        if self._drag in ("paint", "erase") and img is not None:
            self._paint_line(img[0], img[1], erase=(self._drag == "erase"))

        if img is not None:
            col, row = img
            self.hovered.emit(int(col), int(row), float(self.case.hu[row, col]))
        if self.tool in (C.TOOL_BRUSH, C.TOOL_ERASER):
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag == "pan":
            self._update_cursor()
        self._drag = None
        self._last_paint = None
        self._stroke_allow = None

    def leaveEvent(self, event):
        self._cursor_pos = None
        self.update()
        super().leaveEvent(event)

    # ==================== 编辑操作 ====================
    def _layer_locked(self) -> bool:
        return bool(self.case and self.case.locked.get(self.target_layer, False))

    def _apply_grow(self, col, row):
        if self._layer_locked():
            return
        sel = editing.grow_selection(
            self.case.hu, self.case.body, (row, col),
            self.hu_lo, self.hu_hi, conn=self.grow_conn,
            restrict_body=self.grow_restrict, radius_mm=self.grow_radius_mm,
            px_mm=self.case.px_mm)
        if sel is None or not sel.any():
            return
        self.case.undo.push(self.case.label)
        self.case.label[sel] = self.target_layer
        self.rebuild_overlay()
        self.update()
        self.edited.emit()

    def _hu_allow(self):
        """画笔/橡皮的 HU 约束掩膜；未开启限制时返回 None。"""
        if not self.brush_limit_hu:
            return None
        return (self.case.hu >= self.hu_lo) & (self.case.hu <= self.hu_hi)

    def _begin_paint(self, col, row, erase):
        if not erase and self._layer_locked():
            return
        self.case.undo.push(self.case.label)
        self._drag = "erase" if erase else "paint"
        self._last_paint = (col, row)
        self._stroke_allow = self._hu_allow()
        self._paint_disk(col, row, erase)

    def _paint_disk(self, col, row, erase):
        r = max(0.5, self.brush_mm / self.case.px_mm)
        if erase:
            editing.erase_disk(self.case.label, row, col, r, self._stroke_allow)
        else:
            editing.paint_disk(self.case.label, row, col, r, self.target_layer,
                               self._stroke_allow)
        self.rebuild_overlay()
        self.update()
        self.edited.emit()

    def _paint_line(self, col, row, erase):
        lc = self._last_paint
        if lc is None:
            self._paint_disk(col, row, erase)
            return
        dist = math.hypot(col - lc[0], row - lc[1])
        steps = max(1, int(dist))
        r = max(0.5, self.brush_mm / self.case.px_mm)
        for i in range(steps + 1):
            t = i / steps
            c = int(round(lc[0] + (col - lc[0]) * t))
            rr = int(round(lc[1] + (row - lc[1]) * t))
            if erase:
                editing.erase_disk(self.case.label, rr, c, r, self._stroke_allow)
            else:
                editing.paint_disk(self.case.label, rr, c, r, self.target_layer,
                                   self._stroke_allow)
        self._last_paint = (col, row)
        self.rebuild_overlay()
        self.update()
        self.edited.emit()

    # ==================== 杂项 ====================
    def _update_cursor(self):
        if self.tool in (C.TOOL_BRUSH, C.TOOL_ERASER, C.TOOL_GROW):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
