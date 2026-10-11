# -*- coding: utf-8 -*-
"""主窗口：菜单栏 + 三栏布局 + 底部编辑工具条 + 状态栏，以及各控件信号连线。"""
import os
import time

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
    QLabel, QMessageBox, QFileDialog, QApplication, QProgressDialog,
)

from app import constants as C
from app import dicom_io
from app import export
from app import project
from app import segmentation
from app import settings
from app.case_model import CaseModel
from app.sample_data import load_sample_cases
from app.workers import SegmentWorker
from ui.image_view import ImageView
from ui.panels import CasePanel, RightPanel, EditToolbar
from ui.settings_dialog import SettingsDialog


def _card(inner: QWidget) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setStyleSheet("#card{background:#FFFFFF;border:1px solid #E3E8F0;border-radius:10px;}")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(inner)
    return f


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{C.APP_NAME} · {C.APP_VERSION}")
        self.resize(1380, 880)
        self.cases = []
        self.current_index = -1
        self._batch = None
        self._project_path = None
        self._dirty = False
        self._export_dir = settings.output_dir()
        if not self._export_dir or not os.path.isdir(self._export_dir):
            self._export_dir = os.path.join(os.getcwd(), "results")
        if not os.path.isdir(self._export_dir):
            self._export_dir = os.path.expanduser("~")

        try:
            self.cases = load_sample_cases()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "缺少示例数据", str(e))

        self._build_ui()
        self._build_menu()
        self._connect()

        if self.cases:
            self.case_panel.set_cases(self.cases)
            self.case_panel.select(0)
        self._set_dirty(False)

    # ==================== 界面 ====================
    def _build_ui(self):
        self.case_panel = CasePanel()
        self.case_panel.setFixedWidth(238)
        self.image = ImageView()
        self.right = RightPanel()
        self.right.setFixedWidth(278)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(_card(self.case_panel))
        center = QFrame()
        center.setObjectName("center")
        center.setStyleSheet("#center{background:#0E1116;border:1px solid #E3E8F0;border-radius:10px;}")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self.image)
        splitter.addWidget(center)
        splitter.addWidget(_card(self.right))
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([238, 860, 278])

        self.toolbar = EditToolbar()

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        lay.addWidget(splitter, 1)
        lay.addWidget(self.toolbar)
        self.setCentralWidget(central)

        # 状态栏
        sb = self.statusBar()
        self.lbl_file = QLabel("未加载")
        self.lbl_wl = QLabel("窗位/宽 — / —")
        self.lbl_hu = QLabel("HU —")
        self.lbl_xy = QLabel("坐标 —")
        self.lbl_ps = QLabel("像素间距 —")
        for w in (self.lbl_file, self.lbl_wl):
            sb.addWidget(w)
        for w in (self.lbl_ps, self.lbl_xy, self.lbl_hu):
            sb.addPermanentWidget(w)

    def _build_menu(self):
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        a = QAction("导入 DICOM 文件夹 …", self)
        a.setShortcut("Ctrl+O")
        a.triggered.connect(self._on_import)
        m_file.addAction(a)
        a = QAction("导入 DICOM 文件 …", self)
        a.triggered.connect(self._on_import_file)
        m_file.addAction(a)
        a = QAction("导出全部病例数据表 (CSV) …", self)
        a.triggered.connect(self._on_export_csv_all)
        m_file.addAction(a)
        a = QAction("导出当前例数据表 (CSV) …", self)
        a.triggered.connect(self._on_export_csv_current)
        m_file.addAction(a)
        a = QAction("导出当前例叠加图 (PNG) …", self)
        a.triggered.connect(self._on_export_png)
        m_file.addAction(a)
        m_file.addSeparator()
        a = QAction("打开工程 …", self)
        a.setShortcut("Ctrl+Shift+O")
        a.triggered.connect(self._on_open_project)
        m_file.addAction(a)
        a = QAction("保存工程", self)
        a.setShortcut("Ctrl+S")
        a.triggered.connect(self._on_save_project)
        m_file.addAction(a)
        a = QAction("工程另存为 …", self)
        a.triggered.connect(self._on_save_project_as)
        m_file.addAction(a)
        m_file.addSeparator()
        a = QAction("退出", self)
        a.setShortcut("Ctrl+Q")
        a.triggered.connect(self.close)
        m_file.addAction(a)

        m_edit = mb.addMenu("编辑(&E)")
        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self._on_undo)
        m_edit.addAction(self.act_undo)
        self.act_redo = QAction("重做", self)
        self.act_redo.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        self.act_redo.triggered.connect(self._on_redo)
        m_edit.addAction(self.act_redo)

        m_view = mb.addMenu("视图(&V)")
        a = QAction("适应窗口", self)
        a.setShortcut("Ctrl+0")
        a.triggered.connect(self.image.fit_to_window)
        m_view.addAction(a)
        a = QAction("放大", self)
        a.setShortcut("Ctrl+=")
        a.triggered.connect(lambda: self.image.zoom_by(1.25))
        m_view.addAction(a)
        a = QAction("缩小", self)
        a.setShortcut("Ctrl+-")
        a.triggered.connect(lambda: self.image.zoom_by(0.8))
        m_view.addAction(a)
        m_view.addSeparator()
        for text, sel in (("显示全部图层", None),
                          ("只看 皮下脂肪 SAT", C.SAT),
                          ("只看 内脏脂肪 VAT", C.VAT),
                          ("只看 骨骼肌 SMA", C.SMA)):
            a = QAction(text, self)
            a.triggered.connect(lambda _=False, s=sel: self._set_only(s))
            m_view.addAction(a)
        self.act_alpha = QAction("半透明叠加", self, checkable=True)
        self.act_alpha.setChecked(True)
        self.act_alpha.toggled.connect(self._on_alpha)
        m_view.addSeparator()
        m_view.addAction(self.act_alpha)

        m_seg = mb.addMenu("分割(&S)")
        a = QAction("一键自动分割", self)
        a.setShortcut("F5")
        a.triggered.connect(self._on_auto)
        m_seg.addAction(a)
        a = QAction("批量自动分割（全部病例）", self)
        a.setShortcut("F6")
        a.triggered.connect(self._on_batch)
        m_seg.addAction(a)
        a = QAction("重置为自动结果", self)
        a.triggered.connect(self._on_reset)
        m_seg.addAction(a)

        m_set = mb.addMenu("设置(&T)")
        a = QAction("参数与选项 …", self)
        a.triggered.connect(self._on_settings)
        m_set.addAction(a)

        m_help = mb.addMenu("帮助(&H)")
        a = QAction("使用说明", self)
        a.triggered.connect(self._on_help)
        m_help.addAction(a)
        a = QAction("关于", self)
        a.triggered.connect(self._on_about)
        m_help.addAction(a)

    def _connect(self):
        self.case_panel.caseSelected.connect(self.load_case)
        self.case_panel.importRequested.connect(self._on_import)
        self.case_panel.autoSegRequested.connect(self._on_auto)

        self.image.hovered.connect(self._on_hover)
        self.image.edited.connect(self._on_edited)
        self.image.wlChanged.connect(self._on_wl)

        self.right.visibilityChanged.connect(self._on_visibility)
        self.right.opacityChanged.connect(self._on_opacity)
        self.right.lockChanged.connect(self._on_lock)
        self.right.clearRequested.connect(self._on_clear)
        self.right.resetRequested.connect(self._on_reset)

        self.toolbar.toolChanged.connect(self.image.set_tool)
        self.toolbar.toolChanged.connect(self._on_tool)
        self.toolbar.undoRequested.connect(self._on_undo)
        self.toolbar.redoRequested.connect(self._on_redo)
        self.toolbar.brushChanged.connect(self.image.set_brush_mm)
        self.toolbar.targetChanged.connect(self._on_target)
        self.toolbar.huRangeChanged.connect(self.image.set_hu_range)
        self.toolbar.brushLimitChanged.connect(self.image.set_brush_limit_hu)
        self.toolbar.growRadiusChanged.connect(self.image.set_grow_radius)
        self.toolbar.growConnChanged.connect(self.image.set_grow_conn)
        self.toolbar.growRestrictChanged.connect(self.image.set_grow_restrict)

    # ==================== 病例 ====================
    def current_case(self):
        if 0 <= self.current_index < len(self.cases):
            return self.cases[self.current_index]
        return None

    def load_case(self, i):
        if not (0 <= i < len(self.cases)):
            return
        self.current_index = i
        case = self.cases[i]
        self.image.set_case(case)
        self.right.bind_case(case)
        self.toolbar.sync_layer(self.toolbar.cmb_layer.currentData())
        self._refresh()
        m = case.meta
        self.lbl_file.setText(
            f"{case.name} · {m.get('manufacturer', '-')} · 层厚 {m.get('slice_thickness', '-')} mm "
            f"· {m.get('protocol', '')}")
        self.lbl_ps.setText(f"像素间距 {case.px_mm:.3f} mm")
        self._on_wl(int(case.wl), int(case.ww))

    def _refresh(self):
        case = self.current_case()
        if case is None:
            return
        self.right.refresh(case.areas(), case.is_edited())
        self.toolbar.set_undo_enabled(case.undo.can_undo(), case.undo.can_redo())
        self.act_undo.setEnabled(case.undo.can_undo())
        self.act_redo.setEnabled(case.undo.can_redo())
        self.case_panel.mark_edited(self.current_index, case.is_edited())

    # ==================== 图像事件 ====================
    def _on_hover(self, col, row, hu):
        self.lbl_hu.setText(f"HU {hu:.0f}")
        self.lbl_xy.setText(f"坐标 ({col}, {row})")

    def _on_wl(self, wl, ww):
        self.lbl_wl.setText(f"窗位 {wl} / 窗宽 {ww}")

    def _on_edited(self):
        self._set_dirty(True)
        self._refresh()

    # ==================== 图层 ====================
    def _on_visibility(self, lbl, on):
        case = self.current_case()
        if case is None:
            return
        case.visible[lbl] = on
        self.image.rebuild_overlay()
        self.image.update()

    def _on_opacity(self, lbl, v):
        case = self.current_case()
        if case is None:
            return
        case.opacity[lbl] = v
        self.image.rebuild_overlay()
        self.image.update()

    def _on_lock(self, lbl, on):
        case = self.current_case()
        if case is not None:
            case.locked[lbl] = on

    def _on_clear(self, lbl):
        case = self.current_case()
        if case is None:
            return
        case.undo.push(case.label)
        case.label[case.label == lbl] = C.BG
        self.image.rebuild_overlay()
        self.image.update()
        self._set_dirty(True)
        self._refresh()
        self.statusBar().showMessage(f"已清空 {C.LAYER_CN[lbl]} 层", 2500)

    def _set_only(self, sel):
        case = self.current_case()
        if case is None:
            return
        for lbl in C.LAYERS:
            on = (sel is None) or (lbl == sel)
            case.visible[lbl] = on
            row = self.right.rows[lbl]
            row.chk.blockSignals(True)
            row.chk.setChecked(on)
            row.chk.blockSignals(False)
        self.image.rebuild_overlay()
        self.image.update()

    def _on_alpha(self, on):
        case = self.current_case()
        if case is None:
            return
        alpha = C.DEFAULT_OPACITY if on else {l: 0.9 for l in C.LAYERS}
        for lbl in C.LAYERS:
            case.opacity[lbl] = alpha[lbl]
            row = self.right.rows[lbl]
            row.sl.blockSignals(True)
            row.sl.setValue(int(round(alpha[lbl] * 100)))
            row.sl.blockSignals(False)
        self.image.rebuild_overlay()
        self.image.update()

    # ==================== 工具 / 编辑 ====================
    def _on_tool(self, tool):
        self.statusBar().showMessage(f"当前工具：{C.TOOL_CN[tool]}（中/右键平移，滚轮缩放）", 3000)

    def _on_target(self, lbl):
        self.image.set_target_layer(lbl)
        self.toolbar.sync_layer(lbl)
        self.image.set_hu_range(*C.LAYER_HU[lbl])

    def _on_undo(self):
        case = self.current_case()
        if case is None:
            return
        st = case.undo.undo(case.label)
        if st is None:
            self.statusBar().showMessage("无可撤销的操作", 2000)
            return
        case.label = st
        self.image.rebuild_overlay()
        self.image.update()
        self._set_dirty(True)
        self._refresh()

    def _on_redo(self):
        case = self.current_case()
        if case is None:
            return
        st = case.undo.redo(case.label)
        if st is None:
            self.statusBar().showMessage("无可重做的操作", 2000)
            return
        case.label = st
        self.image.rebuild_overlay()
        self.image.update()
        self._set_dirty(True)
        self._refresh()

    # ==================== 分割 ====================
    def _on_auto(self):
        case = self.current_case()
        if case is None:
            return
        case.ensure_loaded()
        if case.px_mm <= 0:
            QMessageBox.warning(self, "无法分割",
                                "该切片的文件头缺少 PixelSpacing（像素间距），无法计算面积。")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            label, body = segmentation.segment_v3(case.hu, case.px_mm, settings.v3_params())
        finally:
            QApplication.restoreOverrideCursor()
        case.undo.push(case.label)
        case.auto_label = label.copy()
        case.label = label.copy()
        case.body = body
        self.image.rebuild_overlay()
        self.image.update()
        self._set_dirty(True)
        self._refresh()
        self.statusBar().showMessage("已完成 v3 自动分割", 3000)

    def _on_batch(self):
        """批量自动分割全部病例（真实 DICOM 走后台线程，内置示例就地处理）。"""
        if not self.cases:
            return
        if getattr(self, "_batch", None) is not None:
            self.statusBar().showMessage("批量分割正在进行中…", 2000)
            return

        n_ok = n_fail = 0
        # 无源文件路径的（内置示例）已在内存中，直接就地分割
        path_jobs = []
        for c in self.cases:
            path = c.meta.get("path")
            if path:
                path_jobs.append((path, path))
                continue
            try:
                c.ensure_loaded()
                if c.px_mm <= 0:
                    raise ValueError("缺少 PixelSpacing")
                label, body = segmentation.segment_v3(c.hu, c.px_mm, settings.v3_params())
                c.apply_segmentation(c.hu, label, body)
                n_ok += 1
            except Exception:  # noqa: BLE001
                n_fail += 1

        if path_jobs:
            self._run_batch_worker(path_jobs, n_ok, n_fail)
        else:
            self._after_batch(n_ok, n_fail)

    def _run_batch_worker(self, path_jobs, n_ok, n_fail):
        by_path = {c.meta.get("path"): c for c in self.cases if c.meta.get("path")}

        dlg = QProgressDialog("正在批量自动分割…", "取消", 0, len(path_jobs), self)
        dlg.setWindowTitle("批量自动分割")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)

        thread = QThread(self)
        worker = SegmentWorker(path_jobs, settings.v3_params())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        self._batch = (thread, worker, dlg)
        result = {"ok": 0, "fail": 0}

        def on_one(key, hu, label, body):
            c = by_path.get(key)
            if c is None:
                return
            c.apply_segmentation(hu, label, body)
            if self.current_case() is c:
                self.image.rebuild_overlay()
                self.image.update()
                self._refresh()

        def on_progress(done, total, _key):
            dlg.setValue(done)

        def on_done(ok, failed):
            result["ok"], result["fail"] = ok, failed
            thread.quit()

        worker.one_done.connect(on_one)
        worker.progress.connect(on_progress)
        worker.all_done.connect(on_done)
        dlg.canceled.connect(thread.requestInterruption)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._after_batch(n_ok + result["ok"], n_fail + result["fail"], dlg))
        thread.start()

    def _after_batch(self, n_ok, n_fail, dlg=None):
        if dlg is not None:
            dlg.close()
        self._batch = None
        if n_ok:
            self._set_dirty(True)
        self.image.rebuild_overlay()
        self.image.update()
        self._refresh()
        self.statusBar().showMessage(
            f"批量分割完成：成功 {n_ok}，失败 {n_fail}", 6000)

    def _on_reset(self):
        case = self.current_case()
        if case is None:
            return
        if case.reset_to_auto():
            self.image.rebuild_overlay()
            self.image.update()
            self._set_dirty(True)
            self._refresh()
            self.statusBar().showMessage("已重置为自动结果", 2500)
        else:
            self.statusBar().showMessage("当前即为自动结果", 2000)

    def _on_import(self, _checked=False):
        """导入 DICOM 文件夹（递归）。"""
        d = QFileDialog.getExistingDirectory(self, "选择 DICOM 文件夹")
        if not d:
            return
        self._import_dir(d)

    def _on_import_file(self):
        """导入单个 DICOM 文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 DICOM 文件", "",
            "DICOM 文件 (*.dcm *.DCM *.ima *.IMA);;所有文件 (*)")
        if not path:
            return
        try:
            meta = dicom_io.scan_file(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导入失败", str(e))
            return
        if not meta.ok:
            QMessageBox.warning(self, "无法读取", f"{meta.display_name}\n{meta.error}")
            return
        self._set_cases([CaseModel.from_dicom(meta)], skipped=[])

    def _import_dir(self, dirpath):
        try:
            metas = dicom_io.scan_folder(dirpath)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导入失败", str(e))
            return
        ok = [m for m in metas if m.ok]
        skipped = [m for m in metas if not m.ok]
        if not ok:
            QMessageBox.warning(self, "没有可用病例",
                                f"在所选文件夹中未找到可读取的 DICOM。\n"
                                f"跳过 {len(skipped)} 个文件。")
            return
        self._set_cases([CaseModel.from_dicom(m) for m in ok], skipped)

    def _set_cases(self, cases, skipped):
        """替换当前病例列表并选中第一例。"""
        self.cases = cases
        self.current_index = -1
        self._project_path = None
        self.case_panel.set_cases(self.cases)
        self.case_panel.select(0)
        self._set_dirty(False)

        msg = f"已导入 {len(cases)} 例"
        if skipped:
            msg += f"，跳过 {len(skipped)} 个无法读取的文件"
        self.statusBar().showMessage(msg, 6000)

        # 缺失 PixelSpacing 的（可载入但不可算面积）单独提示（FR-1.4）
        missing = [c for c in cases if c.px_mm <= 0]
        detail = []
        if skipped:
            detail.append(f"跳过 {len(skipped)} 个无法读取的文件（如：{skipped[0].error}）")
        if missing:
            detail.append(f"另有 {len(missing)} 例缺少 PixelSpacing，无法计算面积")
        if detail:
            QMessageBox.information(self, "导入完成", msg + "\n\n" + "\n".join(detail))

    # ==================== 导出 ====================
    def _default_export_path(self, filename):
        return os.path.join(self._export_dir, filename)

    def _on_export_csv_all(self):
        self._export_csv(self.cases, "全部病例")

    def _on_export_csv_current(self):
        case = self.current_case()
        if case is None:
            self.statusBar().showMessage("没有可导出的病例", 3000)
            return
        self._export_csv([case], case.name)

    def _export_csv(self, cases, tag):
        cases = [c for c in cases if c is not None]
        if not cases:
            self.statusBar().showMessage("没有可导出的病例", 3000)
            return
        default = self._default_export_path(
            f"体成分面积_{tag}_{time.strftime('%Y%m%d_%H%M')}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "导出数据表", default, "CSV 文件 (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            n = export.export_csv(cases, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))
            return
        self._export_dir = os.path.dirname(path)
        self.statusBar().showMessage(f"已导出 {n} 例 → {path}", 8000)

    def _on_export_png(self):
        case = self.current_case()
        if case is None:
            self.statusBar().showMessage("没有可导出的病例", 3000)
            return
        case.ensure_loaded()
        default = self._default_export_path(f"{case.name}_叠加图.png")
        path, _ = QFileDialog.getSaveFileName(self, "导出叠加图", default, "PNG 图片 (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            export.export_overlay_png(case, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))
            return
        self._export_dir = os.path.dirname(path)
        self.statusBar().showMessage(f"已导出叠加图 → {path}", 8000)

    # ==================== 工程 ====================
    def _set_dirty(self, v):
        self._dirty = bool(v)
        name = os.path.basename(self._project_path) if self._project_path else "未命名工程"
        mark = " *" if self._dirty else ""
        self.setWindowTitle(f"{C.APP_NAME} · {C.APP_VERSION} — {name}{mark}")

    def _on_open_project(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开工程", self._export_dir, "体成分工程 (*.bcprj)")
        if not path:
            return
        try:
            cases, idx, _vs = project.load_project(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", str(e))
            return
        self.cases = cases
        self.current_index = -1
        self.case_panel.set_cases(self.cases)
        if self.cases:
            self.case_panel.select(max(0, min(idx, len(self.cases) - 1)))
        self._project_path = path
        self._export_dir = os.path.dirname(path)
        self._set_dirty(False)
        self.statusBar().showMessage(f"已打开工程：{os.path.basename(path)}", 6000)

    def _on_save_project(self):
        if not self._project_path:
            self._on_save_project_as()
            return
        self._save_to(self._project_path)

    def _on_save_project_as(self):
        default = self._project_path or self._default_export_path("体成分工程.bcprj")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存工程", default, "体成分工程 (*.bcprj)")
        if not path:
            return
        if not path.lower().endswith(".bcprj"):
            path += ".bcprj"
        self._save_to(path)

    def _save_to(self, path):
        if not self.cases:
            self.statusBar().showMessage("没有可保存的病例", 3000)
            return
        try:
            project.save_project(path, self.cases, self.current_index)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._project_path = path
        self._export_dir = os.path.dirname(path)
        self._set_dirty(False)
        self.statusBar().showMessage(f"已保存工程：{os.path.basename(path)}", 6000)

    def _maybe_save(self) -> bool:
        """有未保存修改时询问；返回 True=可继续，False=用户取消。"""
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self, "未保存的修改", "当前工程有未保存的修改，是否保存？",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            self._on_save_project()
            return not self._dirty
        if r == QMessageBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event):
        if self._batch is not None and self._batch[0].isRunning():
            self._batch[0].requestInterruption()
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()

    # ==================== 设置 ====================
    def _on_settings(self):
        dlg = SettingsDialog(self)
        if not dlg.exec():
            return
        data = dlg.result_data()
        if not settings.save(data):
            QMessageBox.warning(self, "保存失败", "无法写入用户配置，设置仅本次生效。")
        settings.apply_colors()          # 写回 constants（渲染/导出用）
        if data.get("output_dir"):
            self._export_dir = data["output_dir"]
        self.right.refresh_colors()
        self.image.rebuild_overlay()
        self.image.update()
        self.statusBar().showMessage("设置已更新（v3 参数将在下次自动分割时生效）", 5000)

    # ==================== 帮助 ====================
    def _on_help(self):
        QMessageBox.information(self, "使用说明", (
            "<b>操作流程</b><br>"
            "1. 左侧点击病例 → 中间显示 CT 及彩色分割叠加。<br>"
            "2. <b>窗宽窗位</b>：选择该工具后拖拽左键调节；<br>"
            "&nbsp;&nbsp;&nbsp;滚轮缩放，中键/右键拖拽平移；Ctrl+0 适应窗口。<br>"
            "3. <b>区域生长</b>：选目标层，在图上点击种子点，程序向 HU 相近区域生长。<br>"
            "4. <b>画笔/橡皮</b>：选目标层，按住左键涂抹增 / 删；<br>"
            "&nbsp;&nbsp;&nbsp;勾选「限 HU 范围」时只作用于该 HU 范围内的像素。<br>"
            "5. 右侧查看实时面积；Ctrl+Z 撤销，Ctrl+Y 重做。<br>"
            "6. 三图层互斥：向某层添加像素会自动从其它层移除。"))

    def _on_about(self):
        params = "<br>".join(f"{k}：{v}" for k, v in C.V3_PARAMS)
        QMessageBox.about(self, "关于", (
            f"<b>{C.APP_NAME}</b> {C.APP_VERSION}<br><br>"
            "对标 Slice-O-Matic 的腹部CT体成分面积分析工具。<br>"
            "自动分割算法：v3 阈值几何法（黄=皮下脂肪 / 红=内脏脂肪 / 蓝=骨骼肌）。<br><br>"
            f"<b>v3 参数</b><br>{params}<br><br>"
            "<i>启动默认载入内置示例数据；可「导入 DICOM」载入真实切片。</i>"))

    # ==================== 杂项 ====================
    def _toast(self, text):
        QMessageBox.information(self, "原型演示", text)
