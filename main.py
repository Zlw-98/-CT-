# -*- coding: utf-8 -*-
"""腹部CT体成分面积分析工具 —— 应用入口。

导入真实 DICOM、v3 一键/批量自动分割、人工微调、实时面积、导出 CSV/PNG、工程文件。
启动默认载入内置示例数据。

运行：
    "C:/Users/Levin Zhang/.workbuddy/binaries/python/envs/default/Scripts/python.exe" main.py
"""
import os
import sys

# 保证以项目根目录为包搜索根（支持任意工作目录启动 / 打包）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app import settings
from app.style import apply_style
from ui.main_window import MainWindow


def _install_excepthook():
    """无控制台启动（pythonw）时，把未捕获异常以对话框形式提示，避免静默退出。"""
    import traceback

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            QMessageBox.critical(None, "程序错误", text[-4000:])
        except Exception:
            pass
        sys.stderr.write(text)

    sys.excepthook = hook


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("CT体成分分析")
    apply_style(app)
    settings.apply_colors()   # 载入用户保存的图层颜色
    _install_excepthook()

    try:
        win = MainWindow()
        win.show()
    except Exception as e:  # noqa: BLE001
        import traceback
        QMessageBox.critical(None, "启动失败",
                             "程序初始化时发生错误：\n\n" + traceback.format_exc()[-3000:])
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
