# -*- coding: utf-8 -*-
"""设置对话框：v3 参数 / 默认输出目录 / 图层颜色，可恢复默认。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QLineEdit, QPushButton, QColorDialog, QFileDialog,
    QMessageBox, QWidget,
)

from app import constants as C
from app import settings
from app.style import make_button


class _ColorButton(QPushButton):
    """显示当前颜色的色块按钮，点击打开取色器。"""
    def __init__(self, rgb, parent=None):
        super().__init__(parent)
        self._rgb = tuple(rgb)
        self.setFixedSize(72, 26)
        self._refresh()

    def _refresh(self):
        r, g, b = self._rgb
        self.setStyleSheet(
            f"background:{QColor(r, g, b).name()};border:1px solid #C8D0DC;border-radius:5px;")
        # 亮色用深字、暗色用白字
        fg = "#1A2230" if (r * 0.299 + g * 0.587 + b * 0.114) > 150 else "#FFFFFF"
        self.setText(QColor(r, g, b).name().upper())
        self.setStyleSheet(
            f"background:{QColor(r, g, b).name()};color:{fg};"
            "border:1px solid #C8D0DC;border-radius:5px;")

    def color(self):
        return self._rgb

    def set_color(self, rgb):
        self._rgb = tuple(rgb)
        self._refresh()

    def mousePressEvent(self, event):
        c = QColorDialog.getColor(QColor(*self._rgb), self, "选择颜色")
        if c.isValid():
            self.set_color((c.red(), c.green(), c.blue()))


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(440)
        self._data = settings.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # ---- v3 参数 ----
        gb_v3 = QGroupBox("v3 算法参数")
        form = QFormLayout(gb_v3)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.spins = {}
        for key, name, lo, hi, step in settings.V3_FIELDS:
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setSingleStep(step)
            sp.setDecimals(1)
            sp.setValue(float(self._data["v3"].get(key, C.V3_DEFAULTS[key])))
            sp.setFixedWidth(120)
            form.addRow(name, sp)
            self.spins[key] = sp
        root.addWidget(gb_v3)

        # ---- 输出目录 ----
        gb_out = QGroupBox("默认输出目录")
        oh = QHBoxLayout(gb_out)
        self.ed_dir = QLineEdit(self._data.get("output_dir", ""))
        self.ed_dir.setPlaceholderText("留空则默认使用程序的 results/ 目录")
        btn_browse = make_button("浏览…")
        btn_browse.clicked.connect(self._pick_dir)
        oh.addWidget(self.ed_dir, 1)
        oh.addWidget(btn_browse)
        root.addWidget(gb_out)

        # ---- 颜色 ----
        gb_col = QGroupBox("图层颜色")
        cf = QFormLayout(gb_col)
        cf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.color_btns = {}
        for lbl in C.LAYERS:
            btn = _ColorButton(self._data["colors"].get(str(lbl), C.LAYER_RGB[lbl]))
            cf.addRow(f"{C.LAYER_CN[lbl]} ({C.LAYER_NAME[lbl]})", btn)
            self.color_btns[lbl] = btn
        root.addWidget(gb_col)

        # ---- 按钮 ----
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_reset = box.addButton("恢复默认", QDialogButtonBox.ButtonRole.ResetRole)
        btn_reset.clicked.connect(self._reset_defaults)
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    # ---------- 交互 ----------
    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择默认输出目录",
                                             self.ed_dir.text() or "")
        if d:
            self.ed_dir.setText(d)

    def _reset_defaults(self):
        d = settings.defaults()
        for key, sp in self.spins.items():
            sp.setValue(float(d["v3"][key]))
        self.ed_dir.setText(d["output_dir"])
        for lbl, btn in self.color_btns.items():
            btn.set_color(d["colors"][str(lbl)])

    def _on_accept(self):
        v3 = {k: float(sp.value()) for k, sp in self.spins.items()}
        if v3["fat_lo"] >= v3["fat_hi"]:
            QMessageBox.warning(self, "参数无效", "脂肪 HU 下限必须小于上限。")
            return
        if v3["muscle_lo"] >= v3["muscle_hi"]:
            QMessageBox.warning(self, "参数无效", "肌肉 HU 下限必须小于上限。")
            return
        self.accept()

    def result_data(self) -> dict:
        return {
            "v3": {k: float(sp.value()) for k, sp in self.spins.items()},
            "output_dir": self.ed_dir.text().strip(),
            "colors": {str(lbl): list(btn.color()) for lbl, btn in self.color_btns.items()},
        }
