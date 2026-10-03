---
name: paper-figure
description: "科研数据作图：按论证目标选图，按目标期刊的成品尺寸出图，处理中文字体、色盲安全配色和矢量导出，并渲染成图自查。用于论文配图和“这组数据怎么画”；不做示意图、流程图或架构图。"
---

# 论文数据图

只做数据图：折线、柱状、散点、箱线和小提琴、热力图、误差棒、分布、相关矩阵、多面板。由 agent 直接写 matplotlib 或 seaborn 代码，依赖用 `uv run --with matplotlib --with seaborn ...` 临时加入，不装进全局环境。

## 做法

1. 先弄清这张图要说明什么，以及数据的形态：变量类型、每组样本量、是否偏态或跨量级。论点不清、也无法从论文上下文推断时，问一句。
2. 按论点和数据选图，见 [chart_selection.md](references/chart_selection.md)。维度太多就建议拆成几张图。
3. 按目标期刊的成品尺寸设 `figsize`，字号按成品尺寸设定，见 [journal_specs.md](references/journal_specs.md)。没有指定期刊时问一句，或按论文类型取默认值并说明。
4. 画图时用 `layout="constrained"` 给标签留位置。类别配色用 Okabe-Ito 或 seaborn 的 `colorblind`，同时用线型或 marker 区分；连续色阶用 viridis、magma，正负对称的数据用 RdBu_r，并加带单位的 colorbar。
5. 导出：线条类数据图用 PDF 或 SVG；照片、显微图按期刊要求用 TIFF 或 PNG 等位图，分辨率给足。需要精确成品尺寸时不用 `bbox_inches="tight"`，它会裁掉边距、改变尺寸。
6. 自查：把成图渲染成 PNG，用读图工具看一遍（Claude 用 Read，Codex 用 view_image）。检查有没有缺字方框，标签有没有被裁切或重叠，图例有没有压住数据，多面板编号是否横竖对齐，转成灰度后类别是否还能区分，字号在成品尺寸下是否可读。有问题改完再看。

## 需要主动提醒的问题

用户要求的画法会误导读者时，先说明问题并给出替代方案；用户坚持就照做。常见的有：

- 每组样本很少却只画均值柱，掩盖了分布和样本量。叠加原始数据点，或改用 stripplot、箱线图。
- 误差棒、阴影带、箱线没有说明统计量。图注写明是 SD、SEM、95% CI 还是 IQR，以及 n；只有实际做了显著性检验时，才写检验方法、多重比较校正和星号含义。
- 双 Y 轴放两个无关变量；比例图的 Y 轴不从 0 开始又不标断裂；饼图和 3D 图；rainbow、jet 色图；分类型 x 轴却用折线连起来。

完整清单和替代做法见 [viz_pitfalls.md](references/viz_pitfalls.md)。

## 中文字体

matplotlib 默认字体没有中文，缺字时只发 warning、照样出图。把具体字体名按“西文在前、中文在后”写进 `font.family`，matplotlib 会逐字回退：数字和英文用前一个，中文用后一个。

```python
plt.rcParams.update({
    "font.family": ["Times New Roman", "Songti SC"],
    "axes.unicode_minus": False,  # 负号用 ASCII 字符，避免方框
    "pdf.fonttype": 42,           # 嵌入 TrueType，不用 Type 3
})
```

- 只写 `"serif"` 再配 `font.serif` 列表不会逐字回退，中文仍会变方框。
- 中文字体按本机实际有的选（字体名可从 `matplotlib.font_manager.fontManager.ttflist` 查）：macOS 有 Songti SC，Windows 常见 SimSun、SimHei，Linux 常见 Noto Serif CJK SC。投稿用的 PDF 优先选 TrueType 字体；PingFang 这类 OpenType (CFF) 字体嵌入后，`pdffonts` 会报字体类型不匹配。
- 导出后用 `pdffonts` 确认字体都已嵌入，且没有 Type 3。

## 参考文档

按需读取：

- [chart_selection.md](references/chart_selection.md)：按论点、数据形态和样本量选图。
- [viz_pitfalls.md](references/viz_pitfalls.md)：18 条常见错误和替代做法。
- [journal_specs.md](references/journal_specs.md)：各期刊的栏宽、字号、分辨率和格式要求；以期刊最新的投稿须知为准。
