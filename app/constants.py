# -*- coding: utf-8 -*-
"""全局常量：标签取值、配色、窗宽窗位预设、HU 窗、v3 默认参数、应用元信息。"""

APP_NAME = "腹部CT体成分分析工具"
APP_VERSION = "0.2"

# ---- 标签图取值 ----
BG, SAT, VAT, SMA = 0, 1, 2, 3
LAYERS = (SAT, VAT, SMA)

LAYER_NAME = {SAT: "SAT", VAT: "VAT", SMA: "SMA"}
LAYER_CN = {SAT: "皮下脂肪", VAT: "内脏脂肪", SMA: "骨骼肌"}
# 颜色（与现有结果图一致：黄=皮下脂肪 红=内脏脂肪 蓝=骨骼肌）
LAYER_RGB = {SAT: (255, 215, 0), VAT: (255, 60, 60), SMA: (60, 160, 255)}
LAYER_HEX = {SAT: "#FFD700", VAT: "#FF3C3C", SMA: "#3CA0FF"}
DEFAULT_OPACITY = {SAT: 0.45, VAT: 0.45, SMA: 0.50}
# 区域生长默认 HU 范围（按目标层自动切换）
LAYER_HU = {SAT: (-190, -30), VAT: (-190, -30), SMA: (-29, 150)}

# ---- 窗宽窗位预设 ----
WL_PRESETS = {
    "腹部软组织窗": (40, 350),
    "骨窗": (400, 2000),
    "肺窗": (-600, 1500),
}
DEFAULT_WL = (40, 350)

# ---- 工具 ----
TOOL_WL, TOOL_GROW, TOOL_BRUSH, TOOL_ERASER = "wl", "grow", "brush", "eraser"
TOOL_CN = {
    TOOL_WL: "窗宽窗位",
    TOOL_GROW: "区域生长",
    TOOL_BRUSH: "画笔",
    TOOL_ERASER: "橡皮",
}

# ---- 视图缩放范围（屏幕像素 / 毫米）----
ZOOM_MIN, ZOOM_MAX = 0.02, 40.0

# ---- v3 算法参数（见需求说明书 附录A）----
# 机器可读默认参数，供 app/segmentation.py 使用（键名稳定，设置对话框 WP-7 将改写这些值）
V3_DEFAULTS = {
    "body_hu": -350.0,      # 身体掩膜阈值
    "fat_lo": -190.0,       # 脂肪 HU 窗下限
    "fat_hi": -30.0,        # 脂肪 HU 窗上限
    "muscle_lo": -29.0,     # 肌肉 HU 窗下限
    "muscle_hi": 150.0,     # 肌肉 HU 窗上限
    "sat_mm": 22.0,         # 皮下脂肪测地膨胀厚度上限
    "wall_mm": 12.0,        # 腹壁肌位于皮下脂肪内侧的厚度
    "spine_mm": 24.0,       # 脊柱两侧肌肉的圆盘半径上限
    "front_deg": 50.0,      # 正前排除扇区半角
    "spine_grow_mm": 40.0,  # 脊柱肌洪水填充的生长上限
}

# 展示用（关于对话框）
V3_PARAMS = [
    ("脂肪 HU 窗", "−190 ~ −30"),
    ("肌肉 HU 窗", "−29 ~ +150"),
    ("皮下脂肪厚度 SAT_MM", "22 mm"),
    ("腹壁肌厚度 WALL_MM", "12 mm"),
    ("脊柱肌圆盘半径 SPINE_MM", "24 mm"),
    ("正前排除扇区", "±50°"),
    ("身体掩膜阈值", "−350 HU"),
]
