# -*- coding: utf-8 -*-
"""侧栏与底部工具条：病例列表、图层/面积面板、编辑工具条。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QGroupBox, QCheckBox, QSlider, QComboBox,
    QSpinBox, QToolButton, QButtonGroup, QFrame, QSizePolicy,
)

from app import constants as C
from app.style import make_button


# ============================================================
class CasePanel(QWidget):
    caseSelected = Signal(int)
    importRequested = Signal()
    autoSegRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        title = QLabel("病例列表")
        title.setProperty("class", "sectionTitle")
        lay.addWidget(title)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self.list, 1)

        self.btn_import = make_button("导入 DICOM …")
        self.btn_auto = make_button("一键自动分割", "primary")
        self.btn_import.clicked.connect(self.importRequested.emit)
        self.btn_auto.clicked.connect(self.autoSegRequested.emit)
        lay.addWidget(self.btn_import)
        lay.addWidget(self.btn_auto)

        hint = QLabel("原型演示：当前为内置示例数据")
        hint.setProperty("class", "hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

    def _on_row(self, r):
        if r >= 0:
            self.caseSelected.emit(r)

    def set_cases(self, cases):
        self.list.blockSignals(True)
        self.list.clear()
        for c in cases:
            it = QListWidgetItem(f"{c.name}\n{c.subtitle()}")
            it.setData(Qt.ItemDataRole.UserRole, (c.name, c.subtitle()))
            self.list.addItem(it)
        self.list.blockSignals(False)

    def select(self, i):
        self.list.setCurrentRow(i)

    def mark_edited(self, i, edited):
        it = self.list.item(i)
        if it is None:
            return
        name, sub = it.data(Qt.ItemDataRole.UserRole)
        suffix = "   ·已编辑" if edited else ""
        it.setText(f"{name}\n{sub}{suffix}")


# ============================================================
class _LayerRow(QWidget):
    """单层控件：显示开关 + 色块 + 透明度 + 锁定 + 清空。"""
    def __init__(self, lbl, parent=None):
        super().__init__(parent)
        self.lbl = lbl
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(
            f"background:{C.LAYER_HEX[lbl]};border-radius:3px;")
        h.addWidget(swatch)

        self.chk = QCheckBox(f"{C.LAYER_CN[lbl]} ({C.LAYER_NAME[lbl]})")
        self.chk.setChecked(True)
        h.addWidget(self.chk, 1)

        self.sl = QSlider(Qt.Orientation.Horizontal)
        self.sl.setRange(15, 90)
        self.sl.setValue(int(round(C.DEFAULT_OPACITY[lbl] * 100)))
        self.sl.setFixedWidth(72)
        self.sl.setToolTip("透明度")
        h.addWidget(self.sl)

        self.lock = QCheckBox("锁")
        self.lock.setToolTip("锁定该层，防止误改")
        h.addWidget(self.lock)

        self.clear = QPushButton("清空")
        self.clear.setProperty("class", "small")
        self.clear.setToolTip("清空该层")
        h.addWidget(self.clear)


class RightPanel(QWidget):
    visibilityChanged = Signal(int, bool)
    opacityChanged = Signal(int, float)
    lockChanged = Signal(int, bool)
    clearRequested = Signal(int)
    resetRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        # ---- 图层 ----
        gb_layer = QGroupBox("图层")
        vl = QVBoxLayout(gb_layer)
        vl.setSpacing(4)
        self.rows = {}
        for lbl in C.LAYERS:
            row = _LayerRow(lbl)
            row.chk.toggled.connect(lambda on, l=lbl: self.visibilityChanged.emit(l, on))
            row.sl.valueChanged.connect(
                lambda v, l=lbl: self.opacityChanged.emit(l, v / 100.0))
            row.lock.toggled.connect(lambda on, l=lbl: self.lockChanged.emit(l, on))
            row.clear.clicked.connect(lambda _=False, l=lbl: self.clearRequested.emit(l))
            self.rows[lbl] = row
            vl.addWidget(row)
        lay.addWidget(gb_layer)

        # ---- 面积 ----
        gb_area = QGroupBox("面积（实时）")
        av = QVBoxLayout(gb_area)
        av.setSpacing(6)

        self.badge = QLabel("自动结果")
        self.badge.setProperty("class", "hint")
        av.addWidget(self.badge)

        self.area_labels = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        for i, lbl in enumerate(C.LAYERS):
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{C.LAYER_HEX[lbl]};border-radius:6px;")
            name = QLabel(f"{C.LAYER_CN[lbl]}")
            val = QLabel("—")
            val.setProperty("class", "big")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(dot, i, 0)
            grid.addWidget(name, i, 1)
            grid.addWidget(val, i, 2)
            self.area_labels[lbl] = val
        av.addLayout(grid)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#EEF1F6;")
        av.addWidget(line)

        self.metric_labels = {}
        mg = QGridLayout()
        mg.setVerticalSpacing(4)
        for i, key in enumerate(["fat", "vat_sat", "muscle_hu", "body"]):
            k = QLabel(self._metric_title(key))
            k.setProperty("class", "hint")
            v = QLabel("—")
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            mg.addWidget(k, i, 0)
            mg.addWidget(v, i, 1)
            self.metric_labels[key] = v
        av.addLayout(mg)

        self.btn_reset = make_button("重置为自动结果")
        self.btn_reset.clicked.connect(self.resetRequested.emit)
        av.addWidget(self.btn_reset)
        lay.addWidget(gb_area)

        lay.addStretch(1)

    @staticmethod
    def _metric_title(key):
        return {
            "fat": "总脂肪面积",
            "vat_sat": "VAT / SAT",
            "muscle_hu": "肌肉平均 HU",
            "body": "身体面积",
        }[key]

    def bind_case(self, case):
        """把控件状态同步到某病例（不触发信号）。"""
        for lbl in C.LAYERS:
            row = self.rows[lbl]
            for w, val, fn in (
                (row.chk, case.visible[lbl], row.chk.setChecked),
                (row.lock, case.locked[lbl], row.lock.setChecked),
                (row.sl, int(round(case.opacity[lbl] * 100)), row.sl.setValue),
            ):
                w.blockSignals(True)
                fn(val)
                w.blockSignals(False)

    def refresh(self, areas, edited):
        for lbl in C.LAYERS:
            key = {C.SAT: "SAT", C.VAT: "VAT", C.SMA: "SMA"}[lbl]
            self.area_labels[lbl].setText(f"{areas[key]:.1f} cm²")
        self.metric_labels["fat"].setText(f"{areas['fat']:.1f} cm²")
        self.metric_labels["vat_sat"].setText(
            "—" if areas["vat_sat"] is None else f"{areas['vat_sat']:.2f}")
        self.metric_labels["muscle_hu"].setText(
            "—" if areas["muscle_hu"] is None else f"{areas['muscle_hu']:.1f}")
        self.metric_labels["body"].setText(f"{areas['body']:.1f} cm²")
        if edited:
            self.badge.setText("已人工微调")
            self.badge.setProperty("class", "edited")
        else:
            self.badge.setText("自动结果")
            self.badge.setProperty("class", "hint")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)


# ============================================================
class EditToolbar(QWidget):
    toolChanged = Signal(str)
    undoRequested = Signal()
    redoRequested = Signal()
    brushChanged = Signal(float)
    targetChanged = Signal(int)
    huRangeChanged = Signal(float, float)
    brushLimitChanged = Signal(bool)
    growRadiusChanged = Signal(float)
    growConnChanged = Signal(int)
    growRestrictChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)

        # ---- 工具按钮（互斥）----
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for tool in (C.TOOL_WL, C.TOOL_GROW, C.TOOL_BRUSH, C.TOOL_ERASER):
            b = QToolButton()
            b.setText(C.TOOL_CN[tool])
            b.setCheckable(True)
            b.setToolTip(self._tool_tip(tool))
            b.clicked.connect(lambda _=False, t=tool: self.toolChanged.emit(t))
            self.group.addButton(b)
            self.buttons[tool] = b
            h.addWidget(b)
        self.buttons[C.TOOL_WL].setChecked(True)

        h.addWidget(self._sep())

        # ---- 撤销 / 重做 ----
        self.btn_undo = make_button("撤销")
        self.btn_redo = make_button("重做")
        self.btn_undo.clicked.connect(self.undoRequested.emit)
        self.btn_redo.clicked.connect(self.redoRequested.emit)
        h.addWidget(self.btn_undo)
        h.addWidget(self.btn_redo)

        h.addWidget(self._sep())

        # ---- 目标层 ----
        h.addWidget(self._label("目标层"))
        self.cmb_layer = QComboBox()
        for lbl in C.LAYERS:
            self.cmb_layer.addItem(C.LAYER_CN[lbl], lbl)
        self.cmb_layer.setCurrentIndex(list(C.LAYERS).index(C.SMA))
        self.cmb_layer.currentIndexChanged.connect(
            lambda i: self.targetChanged.emit(self.cmb_layer.itemData(i)))
        h.addWidget(self.cmb_layer)

        # ---- 笔刷半径 ----
        self.lbl_brush = self._label("笔刷")
        h.addWidget(self.lbl_brush)
        self.sl_brush = QSlider(Qt.Orientation.Horizontal)
        self.sl_brush.setRange(2, 60)
        self.sl_brush.setValue(8)
        self.sl_brush.setFixedWidth(96)
        self.sl_brush.valueChanged.connect(
            lambda v: (self.lbl_brush.setText(f"笔刷 {v}mm"), self.brushChanged.emit(float(v))))
        h.addWidget(self.sl_brush)

        h.addWidget(self._sep())

        # ---- HU 范围 ----
        self.lbl_hu = self._label("HU 范围")
        h.addWidget(self.lbl_hu)
        self.sp_lo = QSpinBox()
        self.sp_lo.setRange(-1500, 5000)
        self.sp_lo.setValue(C.LAYER_HU[C.SMA][0])
        self.sp_hi = QSpinBox()
        self.sp_hi.setRange(-1500, 5000)
        self.sp_hi.setValue(C.LAYER_HU[C.SMA][1])
        for sp in (self.sp_lo, self.sp_hi):
            sp.setFixedWidth(82)
            sp.valueChanged.connect(self._emit_hu_range)
        h.addWidget(self.sp_lo)
        h.addWidget(self._label("~"))
        h.addWidget(self.sp_hi)

        self.chk_hu = QCheckBox("限HU")
        self.chk_hu.setChecked(True)
        self.chk_hu.setToolTip("勾选后，画笔 / 橡皮只作用于 HU 在设定范围内的像素")
        self.chk_hu.toggled.connect(self.brushLimitChanged.emit)
        h.addWidget(self.chk_hu)

        # ---- 生长半径 ----
        self.lbl_radius = self._label("生长半径")
        h.addWidget(self.lbl_radius)
        self.sp_radius = QSpinBox()
        self.sp_radius.setRange(0, 120)
        self.sp_radius.setValue(24)
        self.sp_radius.setToolTip("区域生长的半径上限（毫米）")
        self.sp_radius.setFixedWidth(64)
        self.sp_radius.valueChanged.connect(
            lambda v: self.growRadiusChanged.emit(float(v)))
        h.addWidget(self.sp_radius)

        # ---- 连通性 ----
        self.cmb_conn = QComboBox()
        self.cmb_conn.addItem("8 邻域", 8)
        self.cmb_conn.addItem("4 邻域", 4)
        self.cmb_conn.setFixedWidth(80)
        self.cmb_conn.currentIndexChanged.connect(
            lambda i: self.growConnChanged.emit(self.cmb_conn.itemData(i)))
        h.addWidget(self.cmb_conn)

        # ---- 限制体内 ----
        self.chk_body = QCheckBox("限制体内")
        self.chk_body.setChecked(True)
        self.chk_body.setToolTip("生长限制在身体掩膜内，避免溢出体外")
        self.chk_body.toggled.connect(self.growRestrictChanged.emit)
        h.addWidget(self.chk_body)

        h.addStretch(1)
        self.set_tool(C.TOOL_WL)

    # ---------- 辅助 ----------
    def _label(self, text):
        lb = QLabel(text)
        lb.setProperty("class", "hint")
        return lb

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("color:#E3E8F0;")
        return f

    def _tool_tip(self, tool):
        return {
            C.TOOL_WL: "拖拽调节窗宽窗位",
            C.TOOL_GROW: "在图上点击种子点，向 HU 相近区域生长",
            C.TOOL_BRUSH: "按住左键涂抹，加入目标层",
            C.TOOL_ERASER: "按住左键涂抹，擦除回背景",
        }[tool]

    def _emit_hu_range(self):
        self.huRangeChanged.emit(float(self.sp_lo.value()), float(self.sp_hi.value()))

    def set_tool(self, tool):
        """按当前工具启用/禁用相关控件。"""
        is_grow = tool == C.TOOL_GROW
        is_brush = tool in (C.TOOL_BRUSH, C.TOOL_ERASER)
        use_hu = is_grow or is_brush
        self.cmb_layer.setEnabled(True)
        self.lbl_brush.setEnabled(is_brush)
        self.sl_brush.setEnabled(is_brush)
        self.lbl_hu.setEnabled(use_hu)
        self.sp_lo.setEnabled(use_hu)
        self.sp_hi.setEnabled(use_hu)
        self.chk_hu.setEnabled(is_brush)
        self.lbl_radius.setEnabled(is_grow)
        self.sp_radius.setEnabled(is_grow)
        self.cmb_conn.setEnabled(is_grow)
        self.chk_body.setEnabled(is_grow)

    def set_undo_enabled(self, can_undo, can_redo):
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)

    def sync_layer(self, lbl):
        """目标层变化时同步 HU 默认范围。"""
        lo, hi = C.LAYER_HU[lbl]
        for sp, v in ((self.sp_lo, lo), (self.sp_hi, hi)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
