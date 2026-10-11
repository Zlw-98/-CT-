# 项目长期记忆 · 腹部CT体成分分析

## 项目目标
对腹部CT进行自动化身体成分分析（皮下脂肪SAT/内脏脂肪VAT/骨骼肌SMA/肌间脂肪），
替代商业软件 Slice-O-Matic 的手工分割，实现批量化、可复现的定量分析。

## 本机环境（固定事实）
- GPU: NVIDIA RTX 3050 Laptop，**显存仅 4GB**（驱动546.92/CUDA 12.3）
- CPU 16核心；Python 3.11.9(系统) + 3.13.14(WorkBuddy托管)
- **无 conda、无 Docker**；有 git
- 托管venv路径: `C:\Users\Levin Zhang\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
  （已装 pydicom/numpy/scipy/matplotlib/PySide6/SimpleITK/pandas/openpyxl/pywin32）

## 技术约束（重要）
1. **显存4GB 是硬约束** → 优先2D模型；3D nnU-Net 全分辨率必然 OOM
2. **无Docker** → BOA 类方案不可用
3. **无conda** → Comp2Comp/CT-Muscle-Fat-Seg 官方脚本需先装 Miniconda

## 数据约定
- 用户数据在 `ct/`；每次到手先确认是「完整序列」还是「孤立切片」
- 体成分**体积(cm³)** 计算必须依赖连续多层序列；单层只能算**面积(cm²)**
- 输入给 nnUNet 需命名为 `Patient_XXX_0000.nrrd`

## 已选定工具
- **首选**: LuoXiaoC-66/Abdominal-CT-Body-Composition-Analysis（便携版，中文界面）
  - 位置: `software/AutoSegment/`（已下载解压，含4个内置模型权重）
  - License: Apache-2.0（README未标注，LICENSE文件确认为 Apache-2.0）
  - 首次分割需联网自动装 nnUNet 环境，装到 `runtime/`（便携版）或 `.nnunet_env/`（源码版）
  - 源码版: `software/Abdominal-CT-Body-Composition-Analysis/`
- **基线脚本**: `_threshold_v2.py`（纯HU阈值+几何法，零依赖，结果在 results/）

## 相关开源项目评估结论
| 项目 | 结论 |
|---|---|
| LuoXiaoC-66 | ✅ 首选，便携版开箱即用 |
| Comp2Comp (Stanford) | ⚠️ 需conda+py3.9，只用 process_2d |
| CT-Muscle-and-Fat-Seg (Duke) | ⚠️ 需conda+py3.12，nnU-Net ResEnc XL，权重需手动下载 |
| ctpelvimetry | ⚠️ pip可装，但体成分需TotalSegmentator |
| BOA | ❌ 仅Docker分发，本机无Docker |
| AI-Tool4Abdominal-Seg | ❌ 无README/无权重/无协议，仅论文代码片段 |
| CoreSlicer | ❌ 形态学工具，非AI自动分割 |

## 用户偏好
- 需要"零代码/开箱即用"方案（临床科研背景，非计算机专业）
- 关注可视化结果与可导出的Excel/CSV数据
