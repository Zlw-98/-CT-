# 腹部CT体成分面积分析工具 — 详细设计说明书

| 项目 | 内容 |
|---|---|
| 文档名称 | 腹部CT体成分面积分析工具 详细设计说明书 |
| 版本 | v1.0 |
| 日期 | 2026-10-11 |
| 依据 | 《需求说明书_腹部CT体成分面积分析工具.md》v1.1、《_threshold_v3.py》、已实现的高保真可交互原型 |
| 状态标记 | ✅ 原型已实现并已自检 `/` 🟡 逻辑已实现待接入真实管线 `/` ⬜ 待实现 |

---

## 0. 阅读指引与术语

### 0.1 文档目的
把需求说明书中的功能需求（FR-1…FR-8）转化为**可据以编码的模块设计**：给出分层架构、数据模型、
每一模块的职责/接口/关键流程、核心算法的逐步描述、界面控件树与交互状态机、性能预算、异常处理，
并给出「需求 → 设计 → 原型现状」的追溯表，作为下一轮（接入真实 DICOM + v3）施工的依据。

### 0.2 术语
| 术语 | 含义 |
|---|---|
| HU | CT 值，`slope × pixel + intercept`（本数据集 slope=1，intercept=−1024，即 HU=pixel−1024） |
| SAT / VAT / SMA | 皮下脂肪 / 内脏脂肪 / 骨骼肌面积 |
| 标签图 | `uint8` 二维数组，取值 {0 背景, 1 SAT, 2 VAT, 3 SMA}，见 §3.1 |
| Body mask | 身体掩膜，`HU > −350` 填洞+形态学处理后的体部区域 |
| 测地膨胀 | Geodesic dilation：膨胀结果与 `fat` 掩膜求交，用于抗脂肪环断裂 |
| QImage | Qt 位图对象；`build_gray/build_overlay` 的输出经其显示 |
| 目标层 | 当前编辑操作作用到的图层（SAT/VAT/SMA 之一） |

---

## 1. 设计原则

1. **逻辑与界面分离**：`app/` 只依赖 numpy/scipy/pydicom，不含 Qt；`ui/` 只做显示与交互。
   好处：v3 算法可离线单测（复用现有脚本），界面改动不影响算法，便于非专业维护者分头理解。
2. **单一标签图建模**：一个病例一张 `uint8` 标签图，图层互斥由数据结构保证（§3.1），无需在每个编辑路径手写"从其它层扣掉"。
3. **全帧重渲染而非脏矩形**：512×512 下灰度重建 ≈1 ms、叠加层重建 ≈4 ms，整帧 <20 ms。
   不做脏矩形/增量缓存——省下的内存不值得增加代码复杂度（见 §8 实测）。
4. **快照式撤销**：标签图 256 KB/步 × 30 步 ≈ 8 MB，足够；不做差分。
5. **原型可平滑升级为成品**：原型已把"数据模型 / 渲染 / 编辑 / 视图"做成独立模块；
   接入真实 DICOM 时仅需替换数据来源（`sample_data` → `dicom_io`）并新增 `workers/export/project`，其余复用。

---

## 2. 系统架构

### 2.1 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│  界面层  ui/                                                    │
│   main_window.py  ── 菜单栏 / 三栏布局 / 信号连线 / 状态栏        │
│   image_view.py   ── 自绘 QWidget：显示 + 缩放/平移/调窗 + 工具派发 │
│   panels.py       ── CasePanel / RightPanel(图层+面积) / EditToolbar │
└───────────────▲───────────────────────────────┬───────────────┘
     读状态/写编辑 │ 信号(编辑/悬停/窗位变化)          │ 调用算法/渲染
┌───────────────┴───────────────────────────────▼───────────────┐
│  应用逻辑层  app/（纯 numpy/scipy/pydicom，无 Qt）               │
│   constants.py   常量/配色/HU窗/预设/参数                        │
│   case_model.py  病例数据模型（hu/label/auto_label/body/undo/areas）│
│   render.py      build_gray / build_overlay → QImage            │
│   editing.py     paint_disk / erase_disk / grow_selection       │
│   undo.py        UndoStack（快照）                              │
│   segmentation.py  v3 算法（🟡 待接入）                          │
│   dicom_io.py      DICOM 读取与扫描（⬜ 待建）                    │
│   workers.py       批量分割后台线程（⬜ 待建）                    │
│   export.py        导出 CSV/PNG/工程（⬜ 待建）                    │
│   project.py       .bcprj 读写（⬜ 待建）                         │
└───────────────┬───────────────────────────────────────────────┘
                │ numpy / scipy.ndimage / pydicom
┌───────────────▼───────────────────────────────────────────────┐
│  数据层：DICOM 文件、assets/sample.npz（原型示例）、内存数组      │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构（目标态）

```
20261009/
  main.py                    入口：QApplication + 高DPI策略 + 样式 + 异常钩子（✅）
  启动.bat                    一键启动（✅）
  _make_sample.py            示例数据构建（✅，仅构建期）
  _threshold_v3.py           v3 参考算法（既有）
  app/                       应用逻辑（✅ 已建）
    __init__.py  constants.py  style.py  render.py  editing.py
    undo.py  case_model.py  sample_data.py
    # 待建：dicom_io.py  segmentation.py  workers.py  export.py  project.py
  ui/                        界面（✅ 已建）
    __init__.py  image_view.py  panels.py  main_window.py
  assets/sample.npz          原型内置示例数据（✅）
  docs/                      需求说明书 + 本详细设计
  ct/  results/  software/   既有数据/结果/第三方软件
```

### 2.3 技术栈与依赖
| 项 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | 见需求 §4 |
| GUI | PySide6 6.12（Qt6） | 中文界面、跨高DPI |
| 图像/数组 | numpy 2.5 | 全流程数组运算 |
| 形态学/连通域 | scipy.ndimage | 填洞、膨胀、距离变换、label |
| DICOM | pydicom 3.0 | 纯 Python，**不使用 SimpleITK**（避免中文路径问题） |
| 运行环境 | WorkBuddy 托管 venv | `…\.workbuddy\binaries\python\envs\default\Scripts\python.exe` |
| 网络 | 完全离线 | 不上传任何数据 |

### 2.4 线程模型
- **主线程（GUI）**：所有 Qt 控件、渲染、编辑、面积计算。单张自动分割 ≈228 ms，可直接在主线程同步执行。
- **后台线程（⬜ workers.py）**：**批量**自动分割（69 例 × 228 ms ≈ 16 s，必须后台，否则界面冻结）。
  - 采用 `QObject + moveToThread`，信号 `progress/finished_one/finished_all` 经排队连接回主线程；
  - numpy 重计算期间释放 GIL，界面不卡；
  - 单线程顺序处理作业队列，避免内存带宽争抢；结果按 `case_id` 回填，若病例已被移除则丢弃。
- DICOM 像素读取（单文件）主线程同步即可；仅分割批量走线程。

### 2.5 一次典型操作的数据流（自动分割 → 编辑 → 面积刷新）

```
[一键自动分割] → segmentation.segment_v3(hu, px, params) → uint8 label
      → case.label = label; case.auto_label = label.copy()
      → ImageView.rebuild_overlay() → QImage → update()（叠加层显现）
      → RightPanel.refresh(case.areas(), edited=False)（面积数值出现）

[画笔涂抹] → ImageView._begin_paint() push 撤销快照
      → editing.paint_disk(label, …, allow=HU掩膜)（就地改 label）
      → rebuild_overlay() + update();  edited 信号 → MainWindow._on_edited()
      → RightPanel.refresh(case.areas(), edited=True)（数值实时变、出现"已人工微调"）
```

---

## 3. 数据设计

### 3.1 标签图（核心约定）✅
- 类型 `uint8`，形状 `(H, W)`（本数据集 512×512），取值 `0/1/2/3`。
- **互斥语义结构性成立**：一个像素只有一个值 → 任意编辑都不可能产生重叠。
  - 加入某层：`label[mask] = L`（自动从其它层"扣掉"，因为该像素原值被覆盖）；
  - 擦除：`label[mask] = 0`。
- 面积：`count_nonzero(label == L) × (px_mm² / 100)`（cm²）。
- 内存：512×512×1 B = 256 KB/例；69 例 ≈ 18 MB。
- **不采用三层布尔数组**：那会迫使每条编辑路径手写互斥逻辑，是需求 §11 明令要避免的 bug 来源。

### 3.2 `CaseModel` ✅（`app/case_model.py`）
| 字段 | 类型 | 含义 |
|---|---|---|
| `meta` | dict | 匿名/展示用元数据：`id, sex, age, protocol, manufacturer, slice_thickness, pixel_spacing, src` |
| `px_mm` | float | `PixelSpacing[0]`，mm |
| `hu` | float32 (H,W) | HU 图像（惰性/按需加载） |
| `body` | bool (H,W) | 身体掩膜（区域生长/身体面积用） |
| `auto_label` | uint8 (H,W) | v3 自动分割原始结果（**只读参考**） |
| `label` | uint8 (H,W) | 当前工作标签图（可编辑） |
| `undo` | UndoStack | 绑定到 `label` |
| `wl, ww` | float | 当前窗位/窗宽 |
| `visible/opacity/locked` | dict | 每层的显示/透明度/锁定状态 |

关键方法：
```
name -> str                       # meta['id']
shape -> (H,W)
cm2_per_px() -> float             # px_mm²/100
subtitle() -> str                 # "男 · 56岁 · 腹部CT轴位 · 平扫"
is_edited() -> bool               # any(label != auto_label)
reset_to_auto() -> bool           # 先 push 撤销，再 label = auto_label.copy()
areas() -> dict                   # SAT/VAT/SMA/fat/vat_sat/muscle_hu/body（见 §5.5）
```

### 3.3 DICOM 元数据（⬜ `dicom_io.py` 待建）
- 导入时**只读元数据**（`dcmread(path, stop_before_pixels=True)`），69 例亚秒级完成，避免卡顿；像素按需加载。
- 需读取/派生：`PatientID, PatientSex, PatientAge, ProtocolName, SeriesDescription, SliceThickness, PixelSpacing, WindowCenter/Width, RescaleSlope/Intercept, Manufacturer`。
- **增强判断（启发式）**：`ProtocolName/StudyDescription` 含 `增强/动脉/静脉/门脉` 或 `+C/contrast/portal`，或存在 `ContrastBolusAgent` → 增强；否则平扫。
- 缺 `PixelSpacing` → 该例标为"无法计算面积"，在列表与状态栏提示，跳过非致命中止。

### 3.4 工程文件 `.bcprj`（⬜ `project.py` 待建）
- 容器：**zip**。
  - `project.json`：版本、病例列表（顺序、`src` 路径、每例 v3 参数、当前 wl/ww、工具/视图设置、当前单元）。
  - `masks/<case_id>.npz`：压缩存储 `auto_label` 与 `label`（标签图压缩率极高）。
- 载入即完整还原编辑状态（可复现，满足 FR-7.3）。加载前若当前有未保存修改，弹"未保存提示"。

### 3.5 导出格式（⬜ `export.py` 待建）
- **CSV / xlsx**：编码 **UTF-8 with BOM**（`utf-8-sig`），Excel 中文不乱码。
  列：`文件, 患者ID, 性别, 年龄, 序列描述, 层厚mm, 像素间距mm, 身体面积cm², 总脂肪cm², 皮下脂肪SATcm², 内脏脂肪VATcm², 骨骼肌SMAcm², VAT/SAT, 肌肉平均HU, 是否人工编辑`。
- **PNG**：灰度 CT + 三层叠加 + 颜色图例 + 各面积数值（matplotlib 渲染，注册 `msyh.ttc` 中文字体，`axes.unicode_minus=False`）。
- **掩膜（可选）**：导出标签图 NRRD/NIfTI（0/1/2/3），供其它软件使用。

---

## 4. 模块详细设计

> 每个模块列：职责 / 对外接口 / 关键流程 / 异常。✅=已实现，⬜=待建，🟡=逻辑已实现待接入。

### 4.1 `app/constants.py` ✅
职责：集中所有常量，避免魔法数散布。
- 标签：`BG,SAT,VAT,SMA = 0,1,2,3`；`LAYERS=(SAT,VAT,SMA)`。
- 配色：`LAYER_RGB = {SAT:(255,215,0), VAT:(255,60,60), SMA:(60,160,255)}`；`LAYER_HEX`；`DEFAULT_OPACITY={SAT:.45,VAT:.45,SMA:.50}`。
- HU 窗：`LAYER_HU = {SAT:(-190,-30), VAT:(-190,-30), SMA:(-29,150)}`。
- 窗宽窗位预设：`WL_PRESETS={腹部软组织窗:(40,350), 骨窗:(400,2000), 肺窗:(-600,1500)}`，`DEFAULT_WL=(40,350)`。
- 工具：`TOOL_WL/TOOL_GROW/TOOL_BRUSH/TOOL_ERASER` + 中文名。
- 缩放范围：`ZOOM_MIN=0.02, ZOOM_MAX=40.0`（屏幕像素/mm）。
- v3 参数表 `V3_PARAMS`（见附录 A）。

### 4.2 `app/dicom_io.py` ✅
```
@dataclass DicomMeta: path, patient_id, sex, age, protocol, series_desc,
                      slice_thickness, px_mm, window_center/width,
                      rows/cols, slope, intercept, manufacturer, contrast, error
scan_folder(dir, recursive=True) -> list[DicomMeta]   # 只读头；坏文件带 error 保留
scan_file(path) -> DicomMeta
read_hu(path) -> (hu float32, px_mm, DicomMeta)        # 按需读像素算 HU
```
流程：`os.walk` 遍历 → 逐文件 `dcmread(stop_before_pixels=True)` → 抽字段 → 失败则记 `error` 继续。
`ok`=可载入；`can_area`=有 PixelSpacing 可算面积。非 DICOM 在 `scan_folder` 中剔除，其余坏文件保留。
性别已转中文（男/女/其他）；多层/多帧像素在 `read_hu` 中拒绝并提示。

### 4.3 `app/segmentation.py` ✅
职责：v3 阈值几何分割，**纯函数，不含文件 IO**（从 `_threshold_v3.py` 抽出）。
```
default_params() -> dict
body_mask(hu, params=None) -> bool              # 身体掩膜（导入时即算，供"身体面积"）
segment_v3(hu, px_mm, params=None) -> (uint8 label, bool body)
```
参数字典见 `constants.V3_DEFAULTS`（需求附录 A）。逐步算法见 §5.1。
界面"一键自动分割"调 `segment_v3`（单例同步）；批量走 `workers`（WP-4，待建）。

### 4.4 `app/render.py` ✅
职责：把 HU 与标签图转成 Qt 可绘制缓冲；是"屏幕叠加"与"导出 PNG"颜色的唯一来源。
```
build_gray(hu, wl, ww) -> uint8 (H,W)                     # 约 1 ms
build_overlay(label, visible, rgb, opacity, out=None) -> uint8 (H,W,4)   # 约 4 ms；可复用 out 缓冲
gray_to_qimage(gray_u8) -> QImage(Format_Grayscale8, bytesPerLine=W)
overlay_to_qimage(rgba) -> QImage(Format_RGBA8888, bytesPerLine=W*4)     # 注意 RGBA 顺序
```
**关键**：`QImage` 不复制 numpy 缓冲 → 构造后立即 `.copy()`（否则数组被回收后悬空崩溃）。

### 4.5 `app/editing.py` ✅
职责：就地修改标签图的编辑原语。
```
disk_mask(shape, cy, cx, r) -> bool (H,W)
paint_disk(label, cy, cx, r, target, allow=None)   # allow=HU约束掩膜，只在该区域涂
erase_disk(label, cy, cx, r, allow=None)            # 擦回背景
grow_selection(hu, body, seed_yx, lo, hi, conn=8, restrict_body=True,
               radius_mm=0, px_mm=1) -> bool | None  # 种子连通域；种子无效返回 None
```
- `grow_selection` 实现：候选 = `(lo≤HU≤hi) ∩ body ∩ 圆盘(seed, radius)` → `ndimage.label` 取种子所在连通域（≈1 ms）。
- 圆盘半径换算：`r_pix = r_mm / px_mm`。
- `paint_disk/erase_disk` 的 `allow` 即画笔/橡皮的 HU 约束（用户要求，见 §5.3）。

### 4.6 `app/undo.py` ✅
```
class UndoStack(limit=30):
    reset(); can_undo(); can_redo()
    push(current)         # 改动前调用，存 current.copy()
    undo(current) -> arr|None   # 存 current 入 future，弹 past
    redo(current) -> arr|None
```
提交点（每点一步）：一次落笔（stroke 起始，非每次采样）、一次区域生长、清空层、自动分割、重置为自动、载入工程。

### 4.7 `ui/image_view.py` ✅（`ImageView(QWidget)`）
职责：显示与全部图像交互。**自绘 QWidget 而非 QGraphicsView**（单张灰度+单张叠加、需像素级命中，自绘坐标数学更直观）。

信号：`hovered(col,row,hu)`、`edited()`、`wlChanged(wl,ww)`。

视图状态与坐标变换：
```
_zoom 屏幕像素/毫米 ; _sx=px*zoom 屏幕像素/列 ; _sy 屏幕像素/行 ; _ox,_oy 图像左上角屏幕坐标
fit:   zoom = min(W/(w·px), H/(h·px));  ox=(W−w·sx)/2; oy=(H−h·sy)/2
图→屏: wx = ox + ix·sx
屏→图: ix = floor((wx − ox)/sx)            # 用 event.position()（浮点）
滚轮缩放(光标为锚): z=factor; ox = mx − (mx−ox)·z; sx*=z
调窗:  ww = ww0 + dx·2 ; wl = wl0 − dy·2 (ww≥1)
```
工具派发（左键，见 §6.6）：`wl→拖拽调窗`、`grow→点击生长`、`brush/eraser→涂抹`；中/右键始终平移；滚轮始终缩放。

关键方法：`set_case / rebuild_gray / rebuild_overlay / set_window / zoom_by / fit_to_window /
set_tool / set_target_layer / set_brush_mm / set_brush_limit_hu / set_hu_range /
set_grow_radius / set_grow_conn / set_grow_restrict`。
绘制：`paintEvent` 关平滑（最近邻，编辑所见即所得）→ `drawImage(gray)` → `drawImage(overlay)` → 画笔光标圆 → 比例尺。

### 4.8 `ui/panels.py` ✅
- `CasePanel`：`QListWidget`（两行：病例名 / 性别·年龄·序列）+ [导入 DICOM…] + [一键自动分割(primary)] + 提示。
  信号：`caseSelected(int) / importRequested / autoSegRequested`；方法 `set_cases/select/mark_edited`（编辑后追加"·已编辑"）。
- `_LayerRow`：色块 + 显示勾选 + 透明度滑条(15–90) + 锁定 + 清空。
- `RightPanel`：图层组 + 面积组（三层大号数值 + 派生指标 + "自动结果/已人工微调"徽标 + [重置为自动结果]）。
  信号：`visibilityChanged/opacityChanged/lockChanged/clearRequested/resetRequested`；方法 `bind_case(case)/refresh(areas,edited)`。
- `EditToolbar`：互斥工具按钮(QButtonGroup) + 撤销/重做 + 目标层 + 笔刷半径 + HU 范围 + **限HU** 勾选 + 生长半径 + 连通性 + 限制体内。
  信号：`toolChanged/undoRequested/redoRequested/brushChanged/targetChanged/huRangeChanged/brushLimitChanged/growRadiusChanged/growConnChanged/growRestrictChanged`。
  方法 `set_tool`（按工具启用相关控件）、`set_undo_enabled`、`sync_layer`（随目标层切 HU 默认窗）。

### 4.9 `ui/main_window.py` ✅（`MainWindow(QMainWindow)`）
职责：装配菜单栏 + `QSplitter(左|中|右)` + 底部工具条 + 状态栏，并**唯一负责信号连线**（薄装配层）。
- 持有 `cases: list[CaseModel]` 与 `current_index`；`current_case()` 取当前例。
- `load_case(i)`：切换当前例 → `image.set_case` → `right.bind_case` → `toolbar.sync_layer` → `_refresh` → 状态栏文件信息。
- `_refresh()`：更新面积面板、撤销/重做可用态、列表"·已编辑"。
- 编辑回调：`_on_visibility/_on_opacity/_on_lock/_on_clear/_on_reset/_on_undo/_on_redo/_on_alpha/_set_only`。
- 菜单（§6.2）与快捷键（附录 B）。原型中 `_on_import/_on_auto` 弹"原型演示"提示（真实管线未接）。

### 4.10 `app/workers.py` ✅
```
class SegmentWorker(QObject):
    progress   = Signal(int,int,str)            # done,total,key
    one_done   = Signal(str, object, object, object)  # key, hu, label, body
    one_failed = Signal(str, str)               # key, error
    all_done   = Signal(int,int)                # ok,failed
    def __init__(self, jobs): ...               # jobs: [(key, path)]
    @Slot() def run(self): ...
```
约束：worker 不触碰任何控件；用 `Signal(object)` 传 numpy；结果凭 `key`（文件路径）回填。
取消：主线程 `QThread.requestInterruption()`，worker 循环内 `isInterruptionRequested()` 检查。
主线程：`QProgressDialog`（模态、可取消）→ 结果经 `CaseModel.apply_segmentation` 回填；
无路径的内置示例就近在主线程分割。实测 69 例约 17s、界面不冻结。

### 4.11 `app/export.py` ⬜
`export_csv(rows, path)`（utf-8-sig）、`export_overlay_png(case, path)`、`export_mask_nrrd(case, path)`。

### 4.12 `app/project.py` ⬜
`save_project(path, cases, view_state)` / `load_project(path) -> (cases, view_state)`，格式见 §3.4。

---

## 5. 关键算法详细设计

### 5.1 v3 阈值几何法（`segment_v3`）🟡
输入：`hu`（float32，H×W）、`px`（mm/像素）。参数默认见附录 A。

1. **HU 换算**：`hu = pixel·slope + intercept`（本数据集 = pixel − 1024）。
2. **身体掩膜**：`body = fill_holes(hu > −350)` → `binary_opening(iter=2)` → `binary_erosion(iter=3)`；`body.sum()==0` → 返回空。
3. **体内区与离体表距离**：`label(~body)`，取四角的连通域为"体外"；`inside = ~体外`；`dist_surf = distance_transform_edt(inside)·px`；`can = inside & (hu > −350)`。
4. **脂肪/软组织掩膜**：`fat = body & (−190≤hu≤−30)`；`soft = body & (−29≤hu≤150)`。
5. **皮下脂肪 SAT（测地膨胀，抗环断裂）**：`sat = fat & (dist_surf<5mm)`；循环 `round(22/px)` 次 `sat = fat & dilation(sat)`。
6. **内脏脂肪 VAT**：`vat = fat & ~sat`。
7. **腹壁肌环**：`d_sat = distance_transform_edt(~sat)·px`；`wall = can & soft & (d_sat≤12mm) & (dist_surf>6mm)`。
8. **脊柱两侧肌（腰大肌/椎旁肌）**：
   - `bone = body & (hu>200)`；取最大连通块为椎体 `spine`；`d_spine = distance_transform_edt(~spine)·px`；
   - 计算朝向：以椎体质心 `(cy,cx)` 定义"正前方向"；`front = 前向分量 ≥ cos(50°)`（正前 ±50° 扇形）；
   - `posterior = can & soft & (d_spine≤10mm) & ~front`；循环 `round(40/px)` 次在 `can&soft&~front` 内膨胀；再 `& (d_spine≤24mm)` 圆盘封顶；
   - `canal = fill_holes(bone) & ~bone`（椎管脊髓 + 椎体骨髓腔）。
9. **合成**：`muscle = (wall | posterior) & body & ~canal`；输出 `label[sat]=1, label[vat]=2, label[muscle]=3`。
10. **面积**：`count_nonzero(label==L)·px²/100`。

复杂度：以一次 EDT 与少量膨胀为主，**实测 512×512 ≈ 228 ms**（满足 FR-3.3 ≤2s）。
已知局限（须提示人工复核）：脏器与肌肉 HU 重叠、胸部层面语义不严谨、肌间脂肪未单列（并入 VAT）。

### 5.2 区域生长（`grow_selection`）✅
```
cand = (lo ≤ HU ≤ hi) & (body if restrict_body) & (disk(seed, radius) if radius>0)
if not cand[seed]: return None
lab = ndimage.label(cand, struct=8邻域|4邻域)
return lab == lab[seed]              # 布尔选择区
```
结果按覆盖语义赋给目标层（`label[sel]=target`）。**实测 ≈1 ms**。支持连续多种子累积；提交前可预览高亮。

### 5.3 画笔 / 橡皮（含 HU 约束）✅
- 圆盘半径 `r_pix = brush_mm / px`（≥0.5）。
- **HU 约束**（用户明确要求）：勾选"限HU"时，`allow = (hu_lo ≤ HU ≤ hu_hi)`，涂抹仅在 `allow` 内生效；
  一次 stroke 内 `allow` 只算一次（`_stroke_allow`），随连线插值复用到每个采样圆盘，避免重复计算。
- 插值：上一采样点与当前点之间按像素步进补圆盘，保证快速拖动不断线。
- 锁定：目标层 `locked` 时，"增加笔"不生效（擦除不受锁限制）。
- 覆盖语义：`paint_disk` 直接写目标层值 → 自动从其它层扣掉；`erase_disk` 写 0。

### 5.4 窗宽窗位变换（`build_gray`）✅
```
lo = wl − ww/2 ; g = clip((hu − lo)·255/ww, 0, 255) → uint8
```
改为 `g = (hu − (wl−ww/2)) · (255/ww)`。极小图（512²）下直接算式 ≈1 ms，无需 4096 项 LUT。

### 5.5 面积与派生指标（`CaseModel.areas`）✅
```
a = px²/100 (cm²/像素)
SAT/VAT/SMA = count(label==L)·a
总脂肪 = (nSAT+nVAT)·a
VAT/SAT  = nVAT/nSAT   (nSAT=0 → None)
肌肉平均HU = mean(hu[label==SMA])  (空 → None)
身体面积 = count(body)·a
```
`body` 在分割时固化保存，故编辑不改变身体面积。

---

## 6. 界面详细设计

### 6.1 总体布局（对照需求 §6）✅
```
┌───────────────────────────────────────────────────────────────┐
│ 菜单栏: 文件 编辑 视图 分割 帮助                                 │
├──────────────┬────────────────────────────────┬───────────────┤
│ 病例列表      │                                │ 图层           │
│ (两行/例)     │        CT 灰度 + 三层叠加        │ ☑皮下 ☑内脏 ☑骨骼│
│ …            │        可缩放/平移/调窗          │ 透明度/锁/清空   │
│ [导入DICOM…]  │        右下角比例尺              │ 面积(实时)      │
│ [一键自动分割] │                                │ SAT/VAT/SMA +  │
│              │                                │ 派生指标 + 重置  │
├──────────────┴────────────────────────────────┴───────────────┤
│ 工具条: [窗宽窗位][区域生长][画笔][橡皮] │[撤销][重做]│目标层│笔刷│HU范围│限HU│生长半径│连通性│限制体内│
├───────────────────────────────────────────────────────────────┤
│ 状态栏: 文件信息 | 窗位/宽 …            像素间距 | 坐标 | HU      │
└───────────────────────────────────────────────────────────────┘
```
`QSplitter` 支持三栏拖拽调宽；左右栏固定宽约 238 / 278 px；中栏深色底(#0E1116)。

### 6.2 菜单 ✅
| 菜单 | 项 | 快捷键 | 行为 |
|---|---|---|---|
| 文件 | 导入 DICOM… | Ctrl+O | ⬜ 真实导入（原型弹提示） |
| | 导出结果… | | ⬜ 导出 CSV/PNG |
| | 退出 | Ctrl+Q | 关闭 |
| 编辑 | 撤销 / 重做 | Ctrl+Z / Ctrl+Y、Ctrl+Shift+Z | 作用于当前例 |
| 视图 | 适应窗口 | Ctrl+0 | `fit_to_window` |
| | 放大 / 缩小 | Ctrl+= / Ctrl+- | `zoom_by(1.25/0.8)` |
| | 显示全部图层 / 只看 SAT/VAT/SMA | | `_set_only` |
| | 半透明叠加（可勾选） | | 叠加透明度在 0.45↔0.9 间切换 |
| 分割 | 一键自动分割 | F5 | ⬜ 真实分割（原型恢复示例自动结果） |
| | 重置为自动结果 | | `reset_to_auto` |
| 帮助 | 使用说明 / 关于 | | 操作指引 / v3 参数 |

### 6.3 工具条控件顺序 ✅
`[窗宽窗位|区域生长|画笔|橡皮] ─ [撤销|重做] ─ 目标层[皮下脂肪/内脏脂肪/骨骼肌] ─ 笔刷[slider 2–60mm] ─ HU范围[lo]~[hi] ─ ☑限HU ─ 生长半径[0–120mm] ─ [8邻域/4邻域] ─ ☑限制体内`
按工具启用：wl→仅工具按钮；brush/eraser→笔刷+HU+限HU；grow→HU+生长半径+连通性+限制体内。

### 6.4 右侧面板 ✅
- 图层：色块 + 勾选(显示) + 透明度滑条 + 锁 + 清空（三层）。
- 面积：SAT/VAT/SMA 大号 cm²；分割线；总脂肪面积 / VAT-SAT 比 / 肌肉平均 HU / 身体面积；
  顶部徽标"自动结果 / 已人工微调"；底部[重置为自动结果]。

### 6.5 状态栏 ✅
左：`文件名 · 厂商 · 层厚 · 序列描述` 与 `窗位/宽`；右（常驻）：`像素间距`、`坐标(x,y)`、`HU`。

### 6.6 交互状态机（工具 × 鼠标键）✅
| 工具 | 左键 | 中键 | 右键 | 滚轮 |
|---|---|---|---|---|
| 窗宽窗位 | 拖拽调 WW/WL | 平移 | 平移 | 缩放 |
| 区域生长 | 点击种子生长 | 平移 | 平移 | 缩放 |
| 画笔 | 拖拽涂抹(加入目标层) | 平移 | 平移 | 缩放 |
| 橡皮 | 拖拽擦除(回背景) | 平移 | 平移 | 缩放 |
光标：编辑工具=十字；调窗=移动；平移中=握拳。悬停实时上报 HU/坐标。

### 6.7 样式与配色 ✅
- 主题：浅色扁平（`app/style.py` 全局 QSS + `Microsoft YaHei`），图像区深底。
- 图层配色与既有结果图一致：SAT 黄 #FFD700、VAT 红 #FF3C3C、SMA 蓝 #3CA0FF。
- 导出 PNG 图例沿用同一 RGB（`render` 为唯一颜色来源）。

---

## 7. 接口设计

### 7.1 模块关键签名
见 §4 各模块。核心调用链：
`MainWindow → ImageView.set_case/set_*`；`ImageView → render.* / editing.*`；
`MainWindow/Render → CaseModel.areas()/label/auto_label`；`UndoStack ← CaseModel`。

### 7.2 信号/槽一览 ✅
| 发出者 | 信号 | 接收者·处理 |
|---|---|---|
| CasePanel | caseSelected(int) | MainWindow.load_case |
| CasePanel | importRequested / autoSegRequested | MainWindow._on_import / _on_auto |
| ImageView | hovered(col,row,hu) | MainWindow._on_hover（状态栏） |
| ImageView | edited() | MainWindow._on_edited → 刷新面积/撤销态 |
| ImageView | wlChanged(wl,ww) | MainWindow._on_wl（状态栏） |
| RightPanel | visibility/opacity/lock/clear/reset | MainWindow._on_*（改 CaseModel → 重绘） |
| EditToolbar | toolChanged(str) | ImageView.set_tool + MainWindow._on_tool |
| EditToolbar | undo/redoRequested | MainWindow._on_undo/_on_redo |
| EditToolbar | brushChanged(float) | ImageView.set_brush_mm |
| EditToolbar | targetChanged(int) | MainWindow._on_target（设目标层 + 同步 HU 窗） |
| EditToolbar | huRangeChanged(lo,hi) | ImageView.set_hu_range |
| EditToolbar | brushLimitChanged(bool) | ImageView.set_brush_limit_hu |
| EditToolbar | growRadiusChanged/Conn/Restrict | ImageView.set_grow_* |

---

## 8. 性能设计

### 8.1 实测基准（512×512，本机 CPU）
| 操作 | 实测 | 目标 |
|---|---|---|
| v3 自动分割单例 | ~228 ms | ≤2 s（FR-3.3） |
| 灰度重建（调窗） | ~1.1 ms | 流畅 |
| 叠加层重建（编辑后） | ~4.3 ms | — |
| 区域生长（label 连通域） | ~1.1 ms | ≤200 ms（FR-4 画笔/生长） |
| 面积重算（count_nonzero×3） | ~0.1 ms | 实时 |
| 批量自动分割 69 例 | ~16 s | 后台线程 + 进度（FR-3.5） |
| 导入 69 例（仅元数据） | <1 s | ≤30 s（FR-10） |

### 8.2 设计取舍
- 全帧重渲染（整帧 <20 ms），**不做脏矩形**；pan/zoom/调窗不重建叠加层，仅改目标矩形。
- 数组统一 `ascontiguousarray`；`build_overlay` 复用 `out` 缓冲避免每帧分配。
- 批量分割必须后台线程（16 s 会冻界面）。

---

## 9. 异常处理与边界 ⬜（多数随真实管线补入）
| 场景 | 处理 |
|---|---|
| 单个 DICOM 损坏/非 DICOM | 跳过并记入错误列表，不中断批量（FR-10 稳定性） |
| 缺 PixelSpacing | 该例标"无法计算面积"，列表/状态栏提示 |
| 身体掩膜为空（非腹部层面） | `segment_v3` 返回空标签，提示"该层面无法分割" |
| 区域生长种子落在容差外 | `grow_selection` 返回 None，静默忽略 |
| 无 Python 环境/路径变化 | `启动.bat` 检测并中文提示；`main.py` 全局异常钩子弹对话框 |
| 未保存即关闭 | 弹"未保存提示"（⬜ FR-7.4） |
| 图层被锁定后编辑 | 增加笔/生长不生效（擦除不受限） |

---

## 10. 打包与部署（⬜）
- PyInstaller 打包为 exe（`--windowed`），随包携带 `assets/`；`_app_root()` 兼容 frozen（取 exe 目录）。
- 一键启动：`启动.bat`（已提供）→ 调用托管 venv 的 `pythonw.exe` 运行 `main.py`。
- 目标：可拷到无 Python 的机器运行；纯本地离线。

---

## 11. 需求 → 设计 → 原型现状 追溯表

| 需求 | 设计落点 | 原型现状 |
|---|---|---|
| FR-1 数据导入 | `dicom_io` | ✅（文件夹/单文件；启动仍默认内置示例） |
| FR-2 显示与浏览（WW/WL/缩放/平移/状态栏） | `image_view` | ✅（层切换 FR-2.5 预留） |
| FR-3 自动分割（v3 / 参数可调 / ≤2s / 叠加 / 批量） | `segmentation` + `render` + `workers` | ✅ 单例一键 + 批量后台（69 例≈17s） |
| FR-4 交互微调（互斥/区域生长/画笔/橡皮/撤销/实时/视图辅助） | `editing`+`image_view`+`undo`+`panels` | ✅（软边笔刷 ⬜） |
| FR-5 面积与派生指标（自动/人工区分/重置） | `CaseModel.areas`+`RightPanel` | ✅ |
| FR-6 结果导出（CSV/xlsx/PNG/NRRD） | `export` | ⬜ |
| FR-7 批量与工程/会话 | `workers`+`project` | ⬜（多例逐例精修 ✅） |
| FR-8 设置（参数/输出/颜色/恢复默认） | `constants` + 设置对话框 | ⬜（默认值已在 constants） |
| FR-10 稳定性/可复现/可移植/离线 | §9/§10 | 部分 ✅ |

---

## 12. 原型 → 成品 演进路线（差距清单）

1. **抽算法** ✅：v3 已抽到 `app/segmentation.py::segment_v3`（纯函数）；`_make_sample.py` 改为引用它。
2. **接数据** ✅：`app/dicom_io.py` 已建；[导入]接真实 `scan_folder` + 按需 `read_hu`（懒加载）。
3. **接一键分割** ✅：`MainWindow._on_auto` 调 `segment_v3`，写 `label/auto_label/body`，刷新（单例同步）。
4. **批量并发** ✅：`app/workers.py` 已建，批量分割带进度条与取消，结果按路径回填。
5. **导出** ⬜：新增 `app/export.py`（utf-8-sig CSV、PNG 图例、NRRD 可选）。
6. **工程** ⬜：新增 `app/project.py`（zip+npz），加"未保存提示"。
7. **设置** ⬜：参数/输出目录/颜色方案的设置对话框 + 恢复默认。
8. **打磨** ⬜：软边笔刷、视图辅助增强、错误处理、600+ 例性能回归；最后 PyInstaller 打包。

> 原型已把 §1 原则中的"数据模型/渲染/编辑/视图"打牢，第 4–7 步均为**新增文件 + 接线**，不改动已验证的核心。
> §10 待补：`dicom_io`/`segmentation` 的异常处理与 `CaseModel` 懒加载已随 WP-1~3 落地。

---

## 附录 A：v3 参数默认值
| 参数 | 默认 | 含义 |
|---|---|---|
| 脂肪 HU 窗 | −190 ~ −30 | SAT/VAT 判定 |
| 肌肉 HU 窗 | −29 ~ +150 | SMA 判定 |
| `SAT_MM` | 22 mm | 皮下脂肪测地膨胀厚度上限 |
| `WALL_MM` | 12 mm | 腹壁肌位于皮下脂肪内侧厚度 |
| `SPINE_MM` | 24 mm | 脊柱两侧肌圆盘半径上限 |
| 正前排除扇区 | ±50° | 洪水填充排除正前方（主动脉/肠管） |
| 身体阈值 | −350 HU | 身体掩膜 |

## 附录 B：快捷键
| 快捷键 | 功能 |
|---|---|
| Ctrl+O / Ctrl+Q | 导入 / 退出 |
| Ctrl+Z / Ctrl+Y（或 Ctrl+Shift+Z） | 撤销 / 重做 |
| Ctrl+0 / Ctrl+= / Ctrl+- | 适应窗口 / 放大 / 缩小 |
| F5 | 一键自动分割（当前例） |
| F6 | 批量自动分割（全部病例） |
| 滚轮 / 中·右键拖拽 | 缩放 / 平移 |

## 附录 C：文件格式示例
**CSV（UTF-8 BOM）**
```
文件,患者ID,性别,年龄,序列描述,层厚mm,像素间距mm,身体面积cm²,总脂肪cm²,皮下脂肪SATcm²,内脏脂肪VATcm²,骨骼肌SMAcm²,VAT/SAT,肌肉平均HU,是否人工编辑
4404500.dcm,示例病例01,男,056Y,腹部CT轴位 · 平扫,1,0.727,512.9,208.2,75.6,132.6,124.3,1.75,37.6,否
```
**工程 `.bcprj`（zip 内部）**
```
project.json      # 病例列表/参数/视图状态/当前单元
masks/<id>.npz    # auto_label, label（压缩）
```

---

*本文档与实现同步维护；现状标记以原型代码 `app/`、`ui/` 为准。*
