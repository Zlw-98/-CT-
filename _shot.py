# -*- coding: utf-8 -*-
"""开发自检：离屏启动主窗口，截图保存到 results/ 供目视核对布局。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from app.style import apply_style
from ui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    apply_style(app)
    win = MainWindow()
    win.resize(1380, 880)
    win.show()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "prototype_screenshot.png")

    def shot():
        pix = win.grab()
        pix.save(out)
        print("saved", out, pix.width(), "x", pix.height())
        app.quit()

    QTimer.singleShot(1200, shot)
    app.exec()


if __name__ == "__main__":
    main()
